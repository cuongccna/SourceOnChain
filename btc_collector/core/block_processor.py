"""Block processing and UTXO management."""

from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import structlog

from btc_collector.models.blockchain import (
    BlockData, TransactionData, UTXOData, TransactionInputData, AddressData
)
from btc_collector.core.transaction_parser import TransactionParser
from btc_collector.database.manager import DatabaseManager
from btc_collector.utils.time import format_block_time

logger = structlog.get_logger(__name__)


class BlockProcessor:
    """Processes blocks and manages UTXO state."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.tx_parser = TransactionParser()
        self.logger = logger.bind(component="block_processor")
    
    def process_block(self, block_data: Dict[str, Any]) -> bool:
        """
        Process a complete block with all transactions.
        
        This is the main entry point for block processing that:
        1. Parses block metadata
        2. Processes all transactions
        3. Updates UTXO set
        4. Updates address statistics
        5. Saves everything to database
        """
        block_height = block_data['height']
        block_hash = block_data['hash']
        
        self.logger.info("Processing block", 
                        height=block_height, 
                        hash=block_hash,
                        tx_count=len(block_data.get('tx', [])))
        
        try:
            # 1. Parse block metadata
            block_obj = self._parse_block_metadata(block_data)
            
            # 2. Parse all transactions in the block
            transactions, utxos, inputs = self.tx_parser.parse_block_transactions(block_data)
            
            # 3. Process UTXO spending (mark previous UTXOs as spent)
            self._process_utxo_spending(inputs, block_height, format_block_time(block_data['time']))
            
            # 4. Calculate transaction fees (now that we have input values)
            self._calculate_transaction_fees(transactions, inputs)
            
            # 5. Update block total fees
            total_fees = sum(tx.fee_btc for tx in transactions)
            block_obj.total_fees_btc = total_fees
            
            # 6. Process address statistics
            if self.db_manager.config.enable_address_tracking:
                self._process_address_statistics(utxos, inputs, block_height, block_obj.block_time)
            
            # 7. Save everything to database (atomic transaction)
            success = self._save_block_data(block_obj, transactions, utxos, inputs)
            
            if success:
                self.logger.info("Block processed successfully",
                               height=block_height,
                               tx_count=len(transactions),
                               utxo_count=len(utxos),
                               total_fees=float(total_fees))
                return True
            else:
                self.logger.error("Failed to save block data", height=block_height)
                return False
                
        except Exception as e:
            self.logger.error("Block processing failed",
                            height=block_height,
                            error=str(e))
            return False
    
    def _parse_block_metadata(self, block_data: Dict[str, Any]) -> BlockData:
        """Parse block metadata into BlockData object."""
        return BlockData(
            block_height=block_data['height'],
            block_hash=block_data['hash'],
            block_time=format_block_time(block_data['time']),
            tx_count=len(block_data.get('tx', [])),
            total_fees_btc=Decimal('0'),  # Will be calculated later
            block_size_bytes=block_data.get('size'),
            difficulty=Decimal(str(block_data.get('difficulty', 0))),
            nonce=block_data.get('nonce'),
            merkle_root=block_data.get('merkleroot'),
            previous_block_hash=block_data.get('previousblockhash')
        )
    
    def _process_utxo_spending(self, inputs: List[TransactionInputData], 
                              block_height: int, block_time: datetime):
        """Mark UTXOs as spent based on transaction inputs."""
        for input_data in inputs:
            # Skip coinbase inputs
            if not input_data.previous_tx_hash:
                continue
            
            # Mark the referenced UTXO as spent
            success = self.db_manager.mark_utxo_spent(
                tx_hash=input_data.previous_tx_hash,
                vout_index=input_data.previous_vout_index,
                spent_tx_hash=input_data.tx_hash,
                spent_block_height=block_height,
                spent_at=block_time
            )
            
            if not success:
                self.logger.warning("Failed to mark UTXO as spent",
                                  prev_tx=input_data.previous_tx_hash,
                                  prev_vout=input_data.previous_vout_index,
                                  spending_tx=input_data.tx_hash)
    
    def _calculate_transaction_fees(self, transactions: List[TransactionData], 
                                   inputs: List[TransactionInputData]):
        """Calculate transaction fees by looking up input values."""
        # Group inputs by transaction
        tx_inputs = {}
        for input_data in inputs:
            if input_data.tx_hash not in tx_inputs:
                tx_inputs[input_data.tx_hash] = []
            tx_inputs[input_data.tx_hash].append(input_data)
        
        # Calculate fees for each transaction
        for tx in transactions:
            if tx.is_coinbase:
                tx.fee_btc = Decimal('0')
                continue
            
            # Get input values
            input_values = []
            tx_input_list = tx_inputs.get(tx.tx_hash, [])
            
            for input_data in tx_input_list:
                if input_data.previous_tx_hash:
                    # Look up the value of the previous output
                    utxo_value = self.db_manager.get_utxo_value(
                        input_data.previous_tx_hash,
                        input_data.previous_vout_index
                    )
                    
                    if utxo_value is not None:
                        input_values.append(utxo_value)
                    else:
                        self.logger.warning("UTXO value not found",
                                          tx_hash=input_data.previous_tx_hash,
                                          vout=input_data.previous_vout_index)
            
            # Calculate fee
            if input_values:
                total_input_value = sum(input_values)
                tx.total_input_btc = total_input_value
                tx.fee_btc = total_input_value - tx.total_output_btc
            else:
                self.logger.warning("No input values found for transaction", 
                                  tx_hash=tx.tx_hash)
    
    def _process_address_statistics(self, utxos: List[UTXOData], 
                                   inputs: List[TransactionInputData],
                                   block_height: int, block_time: datetime):
        """Update address statistics based on UTXOs and inputs."""
        # Track addresses affected in this block
        address_updates = {}
        
        # Process new UTXOs (received funds)
        for utxo in utxos:
            if not utxo.address:
                continue
            
            if utxo.address not in address_updates:
                # Get existing address stats or create new
                existing_stats = self.db_manager.get_address_stats(utxo.address)
                
                if existing_stats:
                    address_updates[utxo.address] = AddressData(
                        address=utxo.address,
                        script_type=utxo.script_type,
                        first_seen_block=existing_stats['first_seen_block'],
                        last_seen_block=block_height,
                        first_seen_at=existing_stats.get('first_seen_at', block_time),
                        last_seen_at=block_time,
                        total_received_btc=existing_stats['total_received_btc'],
                        total_sent_btc=existing_stats['total_sent_btc'],
                        current_balance_btc=existing_stats['current_balance_btc'],
                        tx_count=existing_stats['tx_count'],
                        utxo_count=0  # Will be recalculated
                    )
                else:
                    # New address
                    address_updates[utxo.address] = AddressData(
                        address=utxo.address,
                        script_type=utxo.script_type,
                        first_seen_block=block_height,
                        last_seen_block=block_height,
                        first_seen_at=block_time,
                        last_seen_at=block_time,
                        total_received_btc=Decimal('0'),
                        total_sent_btc=Decimal('0'),
                        current_balance_btc=Decimal('0'),
                        tx_count=0,
                        utxo_count=0
                    )
            
            # Update received amount
            addr_data = address_updates[utxo.address]
            addr_data.total_received_btc += utxo.value_btc
            addr_data.current_balance_btc += utxo.value_btc
            addr_data.tx_count += 1
            addr_data.utxo_count += 1
        
        # Process spent UTXOs (sent funds)
        for input_data in inputs:
            if not input_data.previous_tx_hash:  # Skip coinbase
                continue
            
            # Get the UTXO being spent to find the address
            utxo_value = self.db_manager.get_utxo_value(
                input_data.previous_tx_hash,
                input_data.previous_vout_index
            )
            
            # Note: In a full implementation, we'd need to get the address
            # from the UTXO being spent. This is simplified for now.
        
        # Save address updates
        for address_data in address_updates.values():
            self.db_manager.save_or_update_address(address_data)
    
    def _save_block_data(self, block: BlockData, transactions: List[TransactionData],
                        utxos: List[UTXOData], inputs: List[TransactionInputData]) -> bool:
        """Save all block data in a single database transaction."""
        try:
            # Save block
            if not self.db_manager.save_block(block):
                return False
            
            # Save transactions
            if not self.db_manager.save_transactions(transactions):
                return False
            
            # Save UTXOs
            if not self.db_manager.save_utxos(utxos):
                return False
            
            # Save transaction inputs
            if not self.db_manager.save_transaction_inputs(inputs):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to save block data",
                            block_height=block.block_height,
                            error=str(e))
            return False
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        sync_state = self.db_manager.get_sync_state()
        
        return {
            'last_processed_block': sync_state.get('last_synced_block_height', 0) if sync_state else 0,
            'is_syncing': sync_state.get('is_syncing', False) if sync_state else False,
            'sync_started_at': sync_state.get('sync_started_at') if sync_state else None,
            'sync_completed_at': sync_state.get('sync_completed_at') if sync_state else None
        }