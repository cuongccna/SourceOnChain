"""Database management and operations."""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import structlog

from btc_collector.models.config import CollectorConfig
from btc_collector.models.blockchain import (
    BlockData, TransactionData, UTXOData, TransactionInputData, AddressData
)
from btc_collector.database.models import (
    Base, Block, Transaction, UTXO, TransactionInput, Address, SyncState
)

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.logger = logger.bind(component="database_manager")
        
        # Create engine with connection pooling
        self.engine = create_engine(
            config.database_url,
            poolclass=QueuePool,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_pre_ping=True,
            echo=False  # Set to True for SQL debugging
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        self.logger.info("Database manager initialized",
                        host=config.db_host,
                        database=config.db_name)
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        self.logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
        self.logger.warning("Database tables dropped")
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.info("Database connection successful")
            return True
        except Exception as e:
            self.logger.error("Database connection failed", error=str(e))
            return False
    
    # Sync State Management
    def get_sync_state(self) -> Optional[Dict[str, Any]]:
        """Get current synchronization state."""
        with self.get_session() as session:
            sync_state = session.query(SyncState).filter_by(chain='BTC').first()
            if sync_state:
                return {
                    'last_synced_block_height': sync_state.last_synced_block_height,
                    'last_synced_block_hash': sync_state.last_synced_block_hash,
                    'is_syncing': sync_state.is_syncing,
                    'sync_started_at': sync_state.sync_started_at,
                    'sync_completed_at': sync_state.sync_completed_at
                }
            return None
    
    def update_sync_state(self, block_height: int, block_hash: str, 
                         is_syncing: bool = False):
        """Update synchronization state."""
        with self.get_session() as session:
            sync_state = session.query(SyncState).filter_by(chain='BTC').first()
            
            if not sync_state:
                sync_state = SyncState(chain='BTC')
                session.add(sync_state)
            
            sync_state.last_synced_block_height = block_height
            sync_state.last_synced_block_hash = block_hash
            sync_state.is_syncing = is_syncing
            
            if not is_syncing:
                sync_state.sync_completed_at = datetime.utcnow()
            
            session.commit()
    
    def set_sync_started(self):
        """Mark synchronization as started."""
        with self.get_session() as session:
            sync_state = session.query(SyncState).filter_by(chain='BTC').first()
            
            if not sync_state:
                sync_state = SyncState(chain='BTC')
                session.add(sync_state)
            
            sync_state.is_syncing = True
            sync_state.sync_started_at = datetime.utcnow()
            session.commit()
    
    # Block Operations
    def save_block(self, block_data: BlockData) -> bool:
        """Save block data to database."""
        try:
            with self.get_session() as session:
                block = Block(
                    block_height=block_data.block_height,
                    block_hash=block_data.block_hash,
                    block_time=block_data.block_time,
                    tx_count=block_data.tx_count,
                    total_fees_btc=block_data.total_fees_btc,
                    block_size_bytes=block_data.block_size_bytes,
                    difficulty=block_data.difficulty,
                    nonce=block_data.nonce,
                    merkle_root=block_data.merkle_root,
                    previous_block_hash=block_data.previous_block_hash
                )
                
                session.add(block)
                session.commit()
                
                self.logger.debug("Block saved", 
                                height=block_data.block_height,
                                hash=block_data.block_hash)
                return True
                
        except Exception as e:
            self.logger.error("Failed to save block",
                            height=block_data.block_height,
                            error=str(e))
            return False
    
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height."""
        with self.get_session() as session:
            return session.query(Block).filter_by(block_height=height).first()
    
    def block_exists(self, height: int) -> bool:
        """Check if block exists."""
        with self.get_session() as session:
            return session.query(Block).filter_by(block_height=height).first() is not None
    
    # Transaction Operations
    def save_transactions(self, transactions: List[TransactionData]) -> bool:
        """Save multiple transactions to database."""
        try:
            with self.get_session() as session:
                tx_objects = []
                
                for tx_data in transactions:
                    tx_obj = Transaction(
                        tx_hash=tx_data.tx_hash,
                        block_height=tx_data.block_height,
                        block_time=tx_data.block_time,
                        tx_index=tx_data.tx_index,
                        input_count=tx_data.input_count,
                        output_count=tx_data.output_count,
                        total_input_btc=tx_data.total_input_btc,
                        total_output_btc=tx_data.total_output_btc,
                        fee_btc=tx_data.fee_btc,
                        is_coinbase=tx_data.is_coinbase,
                        tx_size_bytes=tx_data.tx_size_bytes,
                        tx_weight=tx_data.tx_weight,
                        locktime=tx_data.locktime
                    )
                    tx_objects.append(tx_obj)
                
                session.add_all(tx_objects)
                session.commit()
                
                self.logger.debug("Transactions saved", count=len(transactions))
                return True
                
        except Exception as e:
            self.logger.error("Failed to save transactions", 
                            count=len(transactions), 
                            error=str(e))
            return False
    
    # UTXO Operations
    def save_utxos(self, utxos: List[UTXOData]) -> bool:
        """Save UTXOs to database."""
        try:
            with self.get_session() as session:
                utxo_objects = []
                
                for utxo_data in utxos:
                    utxo_obj = UTXO(
                        tx_hash=utxo_data.tx_hash,
                        vout_index=utxo_data.vout_index,
                        address=utxo_data.address,
                        script_type=utxo_data.script_type,
                        script_hex=utxo_data.script_hex,
                        value_btc=utxo_data.value_btc,
                        is_spent=utxo_data.is_spent,
                        spent_tx_hash=utxo_data.spent_tx_hash,
                        spent_block_height=utxo_data.spent_block_height,
                        spent_at=utxo_data.spent_at
                    )
                    utxo_objects.append(utxo_obj)
                
                session.add_all(utxo_objects)
                session.commit()
                
                self.logger.debug("UTXOs saved", count=len(utxos))
                return True
                
        except Exception as e:
            self.logger.error("Failed to save UTXOs", 
                            count=len(utxos), 
                            error=str(e))
            return False
    
    def mark_utxo_spent(self, tx_hash: str, vout_index: int, 
                       spent_tx_hash: str, spent_block_height: int,
                       spent_at: datetime) -> bool:
        """Mark UTXO as spent."""
        try:
            with self.get_session() as session:
                utxo = session.query(UTXO).filter_by(
                    tx_hash=tx_hash,
                    vout_index=vout_index
                ).first()
                
                if utxo:
                    utxo.is_spent = True
                    utxo.spent_tx_hash = spent_tx_hash
                    utxo.spent_block_height = spent_block_height
                    utxo.spent_at = spent_at
                    session.commit()
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error("Failed to mark UTXO as spent",
                            tx_hash=tx_hash,
                            vout_index=vout_index,
                            error=str(e))
            return False
    
    def get_utxo_value(self, tx_hash: str, vout_index: int) -> Optional[Decimal]:
        """Get UTXO value."""
        with self.get_session() as session:
            utxo = session.query(UTXO).filter_by(
                tx_hash=tx_hash,
                vout_index=vout_index
            ).first()
            
            return utxo.value_btc if utxo else None
    
    # Transaction Input Operations
    def save_transaction_inputs(self, inputs: List[TransactionInputData]) -> bool:
        """Save transaction inputs to database."""
        try:
            with self.get_session() as session:
                input_objects = []
                
                for input_data in inputs:
                    input_obj = TransactionInput(
                        tx_hash=input_data.tx_hash,
                        input_index=input_data.input_index,
                        previous_tx_hash=input_data.previous_tx_hash,
                        previous_vout_index=input_data.previous_vout_index,
                        script_sig_hex=input_data.script_sig_hex,
                        witness_data=input_data.witness_data,
                        sequence_number=input_data.sequence_number
                    )
                    input_objects.append(input_obj)
                
                session.add_all(input_objects)
                session.commit()
                
                self.logger.debug("Transaction inputs saved", count=len(inputs))
                return True
                
        except Exception as e:
            self.logger.error("Failed to save transaction inputs",
                            count=len(inputs),
                            error=str(e))
            return False
    
    # Address Operations
    def save_or_update_address(self, address_data: AddressData) -> bool:
        """Save or update address statistics."""
        try:
            with self.get_session() as session:
                address = session.query(Address).filter_by(
                    address=address_data.address
                ).first()
                
                if address:
                    # Update existing address
                    address.last_seen_block = address_data.last_seen_block
                    address.last_seen_at = address_data.last_seen_at
                    address.total_received_btc = address_data.total_received_btc
                    address.total_sent_btc = address_data.total_sent_btc
                    address.current_balance_btc = address_data.current_balance_btc
                    address.tx_count = address_data.tx_count
                    address.utxo_count = address_data.utxo_count
                else:
                    # Create new address
                    address = Address(
                        address=address_data.address,
                        script_type=address_data.script_type,
                        first_seen_block=address_data.first_seen_block,
                        last_seen_block=address_data.last_seen_block,
                        first_seen_at=address_data.first_seen_at,
                        last_seen_at=address_data.last_seen_at,
                        total_received_btc=address_data.total_received_btc,
                        total_sent_btc=address_data.total_sent_btc,
                        current_balance_btc=address_data.current_balance_btc,
                        tx_count=address_data.tx_count,
                        utxo_count=address_data.utxo_count
                    )
                    session.add(address)
                
                session.commit()
                return True
                
        except Exception as e:
            self.logger.error("Failed to save address",
                            address=address_data.address,
                            error=str(e))
            return False
    
    def get_address_stats(self, address: str) -> Optional[Dict[str, Any]]:
        """Get address statistics."""
        with self.get_session() as session:
            addr_obj = session.query(Address).filter_by(address=address).first()
            
            if addr_obj:
                return {
                    'address': addr_obj.address,
                    'total_received_btc': addr_obj.total_received_btc,
                    'total_sent_btc': addr_obj.total_sent_btc,
                    'current_balance_btc': addr_obj.current_balance_btc,
                    'tx_count': addr_obj.tx_count,
                    'first_seen_block': addr_obj.first_seen_block,
                    'last_seen_block': addr_obj.last_seen_block
                }
            
            return None
    
    def close(self):
        """Close database connections."""
        self.engine.dispose()
        self.logger.info("Database connections closed")