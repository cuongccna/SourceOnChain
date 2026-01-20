"""Transaction parsing and data extraction."""

from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import structlog

from btc_collector.models.blockchain import (
    TransactionData, UTXOData, TransactionInputData
)
from btc_collector.utils.bitcoin import (
    parse_vout, parse_vin, calculate_fee, satoshi_to_btc
)
from btc_collector.utils.time import format_block_time

logger = structlog.get_logger(__name__)


class TransactionParser:
    """Parse Bitcoin transactions and extract structured data."""
    
    def __init__(self):
        self.logger = logger.bind(component="transaction_parser")
    
    def parse_transaction(self, tx_data: Dict[str, Any], block_height: int, 
                         block_time: datetime, tx_index: int) -> Tuple[
                             TransactionData, List[UTXOData], List[TransactionInputData]
                         ]:
        """
        Parse a single transaction and extract all relevant data.
        
        Returns:
            Tuple of (transaction_data, utxo_list, input_list)
        """
        tx_hash = tx_data['txid']
        
        # Parse inputs
        inputs_data = []
        total_input_value = Decimal('0')
        is_coinbase = False
        
        for input_index, vin in enumerate(tx_data.get('vin', [])):
            input_info = parse_vin(vin)
            
            if input_info['is_coinbase']:
                is_coinbase = True
            else:
                # For non-coinbase inputs, we'll need to look up the previous output value
                # This will be handled by the collector when processing UTXO spending
                pass
            
            input_data = TransactionInputData(
                tx_hash=tx_hash,
                input_index=input_index,
                previous_tx_hash=input_info['previous_tx_hash'],
                previous_vout_index=input_info['previous_vout_index'],
                script_sig_hex=input_info['script_sig_hex'],
                witness_data=input_info['witness_data'],
                sequence_number=input_info['sequence_number']
            )
            inputs_data.append(input_data)
        
        # Parse outputs
        outputs_data = []
        total_output_value = Decimal('0')
        
        for vout_index, vout in enumerate(tx_data.get('vout', [])):
            output_info = parse_vout(vout)
            
            utxo_data = UTXOData(
                tx_hash=tx_hash,
                vout_index=vout_index,
                address=output_info['address'],
                script_type=output_info['script_type'],
                script_hex=output_info['script_hex'],
                value_btc=output_info['value_btc']
            )
            outputs_data.append(utxo_data)
            total_output_value += output_info['value_btc']
        
        # Calculate fee (for coinbase transactions, fee is 0)
        fee_btc = Decimal('0')
        if not is_coinbase:
            # Fee calculation will be completed when input values are resolved
            pass
        
        # Create transaction data
        transaction_data = TransactionData(
            tx_hash=tx_hash,
            block_height=block_height,
            block_time=block_time,
            tx_index=tx_index,
            input_count=len(inputs_data),
            output_count=len(outputs_data),
            total_input_btc=total_input_value,
            total_output_btc=total_output_value,
            fee_btc=fee_btc,
            is_coinbase=is_coinbase,
            tx_size_bytes=tx_data.get('size'),
            tx_weight=tx_data.get('weight'),
            locktime=tx_data.get('locktime', 0)
        )
        
        self.logger.debug("Parsed transaction",
                         tx_hash=tx_hash,
                         inputs=len(inputs_data),
                         outputs=len(outputs_data),
                         is_coinbase=is_coinbase)
        
        return transaction_data, outputs_data, inputs_data
    
    def calculate_transaction_fee(self, tx_data: TransactionData, 
                                 input_values: List[Decimal]) -> Decimal:
        """Calculate transaction fee given input values."""
        if tx_data.is_coinbase:
            return Decimal('0')
        
        total_input_value = sum(input_values)
        return calculate_fee(total_input_value, tx_data.total_output_btc)
    
    def parse_block_transactions(self, block_data: Dict[str, Any]) -> Tuple[
        List[TransactionData], List[UTXOData], List[TransactionInputData]
    ]:
        """
        Parse all transactions in a block.
        
        Returns:
            Tuple of (transactions_list, utxos_list, inputs_list)
        """
        block_height = block_data['height']
        block_time = format_block_time(block_data['time'])
        
        all_transactions = []
        all_utxos = []
        all_inputs = []
        
        for tx_index, tx_data in enumerate(block_data.get('tx', [])):
            try:
                tx_data_obj, utxos, inputs = self.parse_transaction(
                    tx_data, block_height, block_time, tx_index
                )
                
                all_transactions.append(tx_data_obj)
                all_utxos.extend(utxos)
                all_inputs.extend(inputs)
                
            except Exception as e:
                self.logger.error("Failed to parse transaction",
                                tx_hash=tx_data.get('txid', 'unknown'),
                                block_height=block_height,
                                error=str(e))
                raise
        
        self.logger.info("Parsed block transactions",
                        block_height=block_height,
                        tx_count=len(all_transactions),
                        utxo_count=len(all_utxos))
        
        return all_transactions, all_utxos, all_inputs
    
    def extract_addresses_from_utxos(self, utxos: List[UTXOData]) -> List[str]:
        """Extract unique addresses from UTXO list."""
        addresses = set()
        
        for utxo in utxos:
            if utxo.address:
                addresses.add(utxo.address)
        
        return list(addresses)
    
    def group_utxos_by_address(self, utxos: List[UTXOData]) -> Dict[str, List[UTXOData]]:
        """Group UTXOs by address."""
        address_utxos = {}
        
        for utxo in utxos:
            if utxo.address:
                if utxo.address not in address_utxos:
                    address_utxos[utxo.address] = []
                address_utxos[utxo.address].append(utxo)
        
        return address_utxos