"""Blockchain data models for Bitcoin."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class BlockData:
    """Block-level data structure."""
    block_height: int
    block_hash: str
    block_time: datetime
    tx_count: int
    total_fees_btc: Decimal
    block_size_bytes: Optional[int] = None
    difficulty: Optional[Decimal] = None
    nonce: Optional[int] = None
    merkle_root: Optional[str] = None
    previous_block_hash: Optional[str] = None


@dataclass
class TransactionData:
    """Transaction-level data structure."""
    tx_hash: str
    block_height: int
    block_time: datetime
    tx_index: int
    input_count: int
    output_count: int
    total_input_btc: Decimal
    total_output_btc: Decimal
    fee_btc: Decimal
    is_coinbase: bool = False
    tx_size_bytes: Optional[int] = None
    tx_weight: Optional[int] = None
    locktime: Optional[int] = None


@dataclass
class UTXOData:
    """UTXO-level data structure."""
    tx_hash: str
    vout_index: int
    address: Optional[str]
    script_type: Optional[str]
    script_hex: Optional[str]
    value_btc: Decimal
    is_spent: bool = False
    spent_tx_hash: Optional[str] = None
    spent_block_height: Optional[int] = None
    spent_at: Optional[datetime] = None


@dataclass
class TransactionInputData:
    """Transaction input data structure."""
    tx_hash: str
    input_index: int
    previous_tx_hash: Optional[str]
    previous_vout_index: Optional[int]
    script_sig_hex: Optional[str]
    witness_data: Optional[Dict[str, Any]]
    sequence_number: int = 0


@dataclass
class AddressData:
    """Address-level aggregated data structure."""
    address: str
    script_type: Optional[str]
    first_seen_block: int
    last_seen_block: int
    first_seen_at: datetime
    last_seen_at: datetime
    total_received_btc: Decimal
    total_sent_btc: Decimal
    current_balance_btc: Decimal
    tx_count: int
    utxo_count: int = 0


@dataclass
class RawBlockResponse:
    """Raw block data from Bitcoin Core RPC."""
    hash: str
    height: int
    time: int
    nTx: int
    size: int
    difficulty: float
    nonce: int
    merkleroot: str
    previousblockhash: Optional[str]
    tx: List[Dict[str, Any]]


@dataclass
class RawTransactionResponse:
    """Raw transaction data from Bitcoin Core RPC."""
    txid: str
    size: int
    weight: int
    locktime: int
    vin: List[Dict[str, Any]]
    vout: List[Dict[str, Any]]