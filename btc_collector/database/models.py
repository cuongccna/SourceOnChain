"""SQLAlchemy database models for Bitcoin data."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Numeric, 
    Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class SyncState(Base):
    """Synchronization state management."""
    __tablename__ = 'sync_state'
    
    id = Column(Integer, primary_key=True)
    chain = Column(String(10), nullable=False, default='BTC', unique=True)
    last_synced_block_height = Column(Integer, nullable=False, default=0)
    last_synced_block_hash = Column(String(64))
    sync_started_at = Column(DateTime(timezone=True))
    sync_completed_at = Column(DateTime(timezone=True))
    is_syncing = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


class Block(Base):
    """Block-level data."""
    __tablename__ = 'blocks'
    
    block_height = Column(Integer, primary_key=True)
    block_hash = Column(String(64), nullable=False, unique=True)
    block_time = Column(DateTime(timezone=True), nullable=False)
    tx_count = Column(Integer, nullable=False, default=0)
    total_fees_btc = Column(Numeric(16, 8), default=0)
    block_size_bytes = Column(Integer)
    difficulty = Column(Numeric(20, 8))
    nonce = Column(Integer)
    merkle_root = Column(String(64))
    previous_block_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_blocks_hash', 'block_hash'),
        Index('idx_blocks_time', 'block_time'),
        Index('idx_blocks_height_desc', 'block_height', postgresql_using='btree'),
    )


class Transaction(Base):
    """Transaction-level data."""
    __tablename__ = 'transactions'
    
    tx_hash = Column(String(64), primary_key=True)
    block_height = Column(Integer, ForeignKey('blocks.block_height', ondelete='CASCADE'), nullable=False)
    block_time = Column(DateTime(timezone=True), nullable=False)
    tx_index = Column(Integer, nullable=False)
    input_count = Column(Integer, nullable=False, default=0)
    output_count = Column(Integer, nullable=False, default=0)
    total_input_btc = Column(Numeric(16, 8), default=0)
    total_output_btc = Column(Numeric(16, 8), default=0)
    fee_btc = Column(Numeric(16, 8), default=0)
    is_coinbase = Column(Boolean, default=False)
    tx_size_bytes = Column(Integer)
    tx_weight = Column(Integer)
    locktime = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_transactions_block_height', 'block_height'),
        Index('idx_transactions_block_time', 'block_time'),
        Index('idx_transactions_fee_desc', 'fee_btc', postgresql_using='btree'),
        Index('idx_transactions_is_coinbase', 'is_coinbase'),
        UniqueConstraint('block_height', 'tx_index', name='idx_transactions_block_position'),
    )


class UTXO(Base):
    """UTXO tracking with spending status."""
    __tablename__ = 'utxos'
    
    utxo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tx_hash = Column(String(64), ForeignKey('transactions.tx_hash', ondelete='CASCADE'), nullable=False)
    vout_index = Column(Integer, nullable=False)
    address = Column(String(62))  # Can be NULL for non-standard outputs
    script_type = Column(String(20))
    script_hex = Column(Text)
    value_btc = Column(Numeric(16, 8), nullable=False)
    is_spent = Column(Boolean, default=False)
    spent_tx_hash = Column(String(64))  # References transactions.tx_hash
    spent_block_height = Column(Integer)  # References blocks.block_height
    spent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('tx_hash', 'vout_index', name='idx_utxos_outpoint'),
        Index('idx_utxos_address', 'address'),
        Index('idx_utxos_is_spent', 'is_spent'),
        Index('idx_utxos_spent_tx', 'spent_tx_hash'),
        Index('idx_utxos_value_desc', 'value_btc', postgresql_using='btree'),
        Index('idx_utxos_script_type', 'script_type'),
        Index('idx_utxos_unspent_address', 'address', 'value_btc', 
              postgresql_where="is_spent = false AND address IS NOT NULL"),
    )


class TransactionInput(Base):
    """Transaction inputs with previous output references."""
    __tablename__ = 'transaction_inputs'
    
    input_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tx_hash = Column(String(64), ForeignKey('transactions.tx_hash', ondelete='CASCADE'), nullable=False)
    input_index = Column(Integer, nullable=False)
    previous_tx_hash = Column(String(64))  # NULL for coinbase
    previous_vout_index = Column(Integer)  # NULL for coinbase
    script_sig_hex = Column(Text)
    witness_data = Column(JSONB)  # For SegWit transactions
    sequence_number = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('tx_hash', 'input_index', name='idx_inputs_position'),
        Index('idx_inputs_previous_outpoint', 'previous_tx_hash', 'previous_vout_index',
              postgresql_where="previous_tx_hash IS NOT NULL"),
    )


class Address(Base):
    """Address-level aggregated statistics."""
    __tablename__ = 'addresses'
    
    address = Column(String(62), primary_key=True)
    script_type = Column(String(20))
    first_seen_block = Column(Integer, nullable=False)
    last_seen_block = Column(Integer, nullable=False)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    total_received_btc = Column(Numeric(16, 8), default=0)
    total_sent_btc = Column(Numeric(16, 8), default=0)
    current_balance_btc = Column(Numeric(16, 8), default=0)
    tx_count = Column(Integer, default=0)
    utxo_count = Column(Integer, default=0)  # Current unspent outputs
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_addresses_balance_desc', 'current_balance_btc', postgresql_using='btree'),
        Index('idx_addresses_tx_count_desc', 'tx_count', postgresql_using='btree'),
        Index('idx_addresses_first_seen', 'first_seen_block'),
        Index('idx_addresses_last_seen', 'last_seen_block'),
        Index('idx_addresses_script_type', 'script_type'),
    )


class DailyStats(Base):
    """Daily aggregated statistics."""
    __tablename__ = 'daily_stats'
    
    stat_date = Column(DateTime(timezone=True), primary_key=True)
    block_count = Column(Integer, default=0)
    tx_count = Column(Integer, default=0)
    total_volume_btc = Column(Numeric(20, 8), default=0)
    total_fees_btc = Column(Numeric(16, 8), default=0)
    avg_tx_size_bytes = Column(Numeric(10, 2))
    avg_fee_per_byte = Column(Numeric(10, 8))
    active_addresses = Column(Integer, default=0)
    new_addresses = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())