"""Data models for normalized time-series data."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass


@dataclass
class NetworkActivityData:
    """Network activity time-series data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Core network metrics
    active_addresses: int
    tx_count: int
    total_tx_volume_btc: Decimal
    avg_tx_value_btc: Decimal
    
    # Additional statistics
    median_tx_value_btc: Optional[Decimal] = None
    total_fees_btc: Optional[Decimal] = None
    avg_fee_per_tx_btc: Optional[Decimal] = None
    avg_tx_size_bytes: Optional[Decimal] = None
    
    # Block-level aggregations
    blocks_mined: Optional[int] = None
    avg_block_size_bytes: Optional[Decimal] = None
    avg_tx_per_block: Optional[Decimal] = None


@dataclass
class UTXOFlowData:
    """UTXO flow time-series data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # UTXO creation/destruction
    utxo_created_count: int
    utxo_spent_count: int
    net_utxo_change: int
    
    # BTC flow analysis
    btc_created: Decimal
    btc_spent: Decimal
    net_utxo_flow_btc: Decimal
    
    # UTXO characteristics
    utxo_created_avg_value_btc: Optional[Decimal] = None
    utxo_spent_avg_value_btc: Optional[Decimal] = None
    avg_utxo_age_days: Optional[Decimal] = None
    median_utxo_age_days: Optional[Decimal] = None
    
    # Coinbase analysis
    coinbase_utxo_created_count: Optional[int] = None
    coinbase_btc_created: Optional[Decimal] = None


@dataclass
class AddressBehaviorData:
    """Address behavior time-series data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Address lifecycle
    new_addresses: int
    dormant_addresses_activated: int
    addresses_with_outflows: Optional[int] = None
    addresses_with_inflows: Optional[int] = None
    
    # Behavioral patterns
    address_churn_rate: Decimal
    address_reuse_rate: Optional[Decimal] = None
    
    # Balance changes
    addresses_balance_increased: Optional[int] = None
    addresses_balance_decreased: Optional[int] = None
    addresses_emptied: Optional[int] = None
    
    # Dormancy analysis
    dormancy_threshold_days: int = 30
    total_dormant_addresses: Optional[int] = None
    dormant_btc_activated: Optional[Decimal] = None


@dataclass
class ValueDistributionData:
    """Value distribution time-series data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Transaction value percentiles
    tx_value_p10: Optional[Decimal] = None
    tx_value_p25: Optional[Decimal] = None
    tx_value_p50: Optional[Decimal] = None
    tx_value_p75: Optional[Decimal] = None
    tx_value_p90: Optional[Decimal] = None
    tx_value_p95: Optional[Decimal] = None
    tx_value_p99: Optional[Decimal] = None
    tx_value_p999: Optional[Decimal] = None
    
    # UTXO value percentiles
    utxo_value_p10: Optional[Decimal] = None
    utxo_value_p25: Optional[Decimal] = None
    utxo_value_p50: Optional[Decimal] = None
    utxo_value_p75: Optional[Decimal] = None
    utxo_value_p90: Optional[Decimal] = None
    utxo_value_p95: Optional[Decimal] = None
    utxo_value_p99: Optional[Decimal] = None
    
    # Fee percentiles
    fee_p10: Optional[Decimal] = None
    fee_p50: Optional[Decimal] = None
    fee_p90: Optional[Decimal] = None
    fee_p99: Optional[Decimal] = None
    
    # Distribution statistics
    tx_value_gini_coefficient: Optional[Decimal] = None
    tx_value_std_dev: Optional[Decimal] = None
    tx_value_skewness: Optional[Decimal] = None


@dataclass
class LargeTransactionData:
    """Large transaction activity time-series data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Dynamic thresholds
    large_tx_threshold_btc: Decimal
    whale_tx_threshold_btc: Decimal
    
    # Large transaction metrics
    large_tx_count: int
    large_tx_volume_btc: Decimal
    large_tx_ratio: Decimal
    large_tx_volume_ratio: Optional[Decimal] = None
    
    # Whale activity
    whale_tx_count: Optional[int] = None
    whale_tx_volume_btc: Optional[Decimal] = None
    whale_tx_ratio: Optional[Decimal] = None
    
    # Transaction characteristics
    avg_large_tx_value_btc: Optional[Decimal] = None
    max_tx_value_btc: Optional[Decimal] = None
    large_tx_avg_fee_btc: Optional[Decimal] = None
    
    # Exchange activity (heuristic)
    potential_exchange_large_tx_count: Optional[int] = None
    potential_exchange_large_tx_volume_btc: Optional[Decimal] = None
    
    # Threshold metadata
    threshold_calculation_window_hours: int = 720
    threshold_percentile: Decimal = Decimal('95.0')
    whale_threshold_percentile: Decimal = Decimal('99.9')


@dataclass
class StatisticalThresholds:
    """Statistical thresholds for dynamic calculations."""
    asset: str
    calculation_timestamp: datetime
    window_hours: int
    
    # Transaction percentiles
    tx_value_p50: Optional[Decimal] = None
    tx_value_p75: Optional[Decimal] = None
    tx_value_p90: Optional[Decimal] = None
    tx_value_p95: Optional[Decimal] = None
    tx_value_p99: Optional[Decimal] = None
    tx_value_p999: Optional[Decimal] = None
    
    # UTXO percentiles
    utxo_value_p95: Optional[Decimal] = None
    utxo_value_p99: Optional[Decimal] = None
    
    # Fee percentiles
    fee_p95: Optional[Decimal] = None
    fee_p99: Optional[Decimal] = None
    
    # Sample sizes
    tx_sample_size: Optional[int] = None
    utxo_sample_size: Optional[int] = None


@dataclass
class NormalizationResult:
    """Result of normalization process."""
    timestamp: datetime
    timeframe: str
    success: bool
    
    # Processed data
    network_activity: Optional[NetworkActivityData] = None
    utxo_flow: Optional[UTXOFlowData] = None
    address_behavior: Optional[AddressBehaviorData] = None
    value_distribution: Optional[ValueDistributionData] = None
    large_tx_activity: Optional[LargeTransactionData] = None
    
    # Processing metadata
    processing_time_ms: Optional[int] = None
    records_processed: Optional[int] = None
    error_message: Optional[str] = None