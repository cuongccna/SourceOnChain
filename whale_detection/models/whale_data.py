"""Data models for whale detection results."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class WhaleThresholds:
    """Whale detection thresholds for a specific timeframe."""
    asset: str
    timeframe: str
    calculation_timestamp: datetime
    calculation_window_hours: int
    
    # Percentile-based thresholds (BTC)
    large_tx_threshold_p95: Decimal
    whale_tx_threshold_p99: Decimal
    ultra_whale_threshold_p999: Decimal
    leviathan_threshold_p9999: Optional[Decimal] = None
    
    # UTXO thresholds
    whale_utxo_threshold_p99: Decimal
    ultra_whale_utxo_threshold_p999: Decimal
    
    # Activity spike thresholds
    whale_count_spike_threshold: Decimal
    whale_volume_spike_threshold: Decimal
    
    # Statistical validation
    threshold_stability_score: Optional[Decimal] = None
    regime_change_detected: bool = False
    sample_size: int = 0
    distribution_skewness: Optional[Decimal] = None
    distribution_kurtosis: Optional[Decimal] = None


@dataclass
class WhaleTransactionData:
    """Whale transaction activity data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Whale transaction counts by tier
    large_tx_count: int
    whale_tx_count: int
    ultra_whale_tx_count: int = 0
    leviathan_tx_count: int = 0
    
    # Whale transaction volumes (BTC)
    large_tx_volume_btc: Decimal
    whale_tx_volume_btc: Decimal
    ultra_whale_tx_volume_btc: Decimal = Decimal('0')
    leviathan_tx_volume_btc: Decimal = Decimal('0')
    
    # Ratios vs total activity
    whale_tx_ratio: Decimal
    whale_volume_ratio: Decimal
    
    # Statistical metrics
    avg_whale_tx_size_btc: Optional[Decimal] = None
    max_whale_tx_size_btc: Optional[Decimal] = None
    whale_tx_median_btc: Optional[Decimal] = None
    
    # Thresholds used
    whale_threshold_used_btc: Decimal
    ultra_whale_threshold_used_btc: Optional[Decimal] = None
    
    # Context
    total_tx_count: int
    total_tx_volume_btc: Decimal


@dataclass
class WhaleUTXOFlowData:
    """Whale UTXO flow data."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Whale UTXO creation
    whale_utxo_created_count: int
    whale_utxo_created_btc: Decimal
    ultra_whale_utxo_created_count: int = 0
    ultra_whale_utxo_created_btc: Decimal = Decimal('0')
    
    # Whale UTXO spending
    whale_utxo_spent_count: int
    whale_utxo_spent_btc: Decimal
    ultra_whale_utxo_spent_count: int = 0
    ultra_whale_utxo_spent_btc: Decimal = Decimal('0')
    
    # Net flows
    whale_net_flow_btc: Decimal
    ultra_whale_net_flow_btc: Decimal = Decimal('0')
    
    # UTXO characteristics
    avg_whale_utxo_age_days: Optional[Decimal] = None
    median_whale_utxo_age_days: Optional[Decimal] = None
    whale_utxo_age_weighted_avg: Optional[Decimal] = None
    
    # Ratios
    whale_utxo_creation_ratio: Decimal = Decimal('0')
    whale_utxo_spending_ratio: Decimal = Decimal('0')
    
    # Coinbase whale UTXOs
    whale_coinbase_utxo_count: int = 0
    whale_coinbase_utxo_btc: Decimal = Decimal('0')
    
    # Thresholds used
    whale_utxo_threshold_used_btc: Decimal
    ultra_whale_utxo_threshold_used_btc: Optional[Decimal] = None
    
    # Context
    total_utxo_created_count: int
    total_utxo_created_btc: Decimal
    total_utxo_spent_count: int
    total_utxo_spent_btc: Decimal


@dataclass
class WhaleBehaviorFlags:
    """Whale behavioral pattern flags."""
    timestamp: datetime
    asset: str
    timeframe: str
    
    # Primary behavior flags
    accumulation_flag: bool
    distribution_flag: bool
    activity_spike_flag: bool
    
    # Secondary flags
    ultra_whale_accumulation_flag: bool = False
    ultra_whale_distribution_flag: bool = False
    whale_dormancy_break_flag: bool = False
    
    # Strength indicators (0-1 scale)
    accumulation_strength: Decimal = Decimal('0')
    distribution_strength: Decimal = Decimal('0')
    activity_spike_strength: Decimal = Decimal('0')
    
    # Statistical context
    whale_count_zscore: Decimal = Decimal('0')
    whale_volume_zscore: Decimal = Decimal('0')
    whale_ratio_zscore: Decimal = Decimal('0')
    
    # Trend analysis
    whale_count_trend_7p: Decimal = Decimal('0')
    whale_volume_trend_7p: Decimal = Decimal('0')
    whale_ratio_trend_7p: Decimal = Decimal('0')
    
    # Pattern persistence
    accumulation_streak: int = 0
    distribution_streak: int = 0
    activity_spike_streak: int = 0
    
    # Confidence metrics
    flag_confidence_score: Decimal = Decimal('0')
    data_quality_score: Decimal = Decimal('1')


@dataclass
class WhaleDetectionResult:
    """Complete whale detection result for a timestamp."""
    timestamp: datetime
    timeframe: str
    success: bool
    
    # Detection results
    thresholds: Optional[WhaleThresholds] = None
    transaction_data: Optional[WhaleTransactionData] = None
    utxo_flow_data: Optional[WhaleUTXOFlowData] = None
    behavior_flags: Optional[WhaleBehaviorFlags] = None
    
    # Processing metadata
    processing_time_ms: Optional[int] = None
    transactions_analyzed: Optional[int] = None
    utxos_analyzed: Optional[int] = None
    error_message: Optional[str] = None
    
    # Data quality metrics
    data_completeness: Optional[float] = None
    threshold_stability: Optional[float] = None
    regime_change_detected: bool = False


@dataclass
class WhaleActivitySummary:
    """Summary of whale activity across timeframes."""
    timestamp: datetime
    
    # Cross-timeframe whale metrics
    whale_activity_score: Decimal  # Composite score 0-1
    whale_trend_strength: Decimal  # Trend strength -1 to 1
    
    # Behavioral consensus
    accumulation_consensus: bool  # Accumulation across multiple timeframes
    distribution_consensus: bool  # Distribution across multiple timeframes
    
    # Activity levels
    whale_activity_level: str  # 'low', 'normal', 'high', 'extreme'
    ultra_whale_activity_level: str
    
    # Risk indicators
    whale_volatility_risk: Decimal  # 0-1 scale
    large_movement_risk: Decimal    # 0-1 scale
    
    # Timeframe-specific data
    timeframe_data: Dict[str, WhaleDetectionResult]


@dataclass
class WhaleAlertData:
    """Whale activity alert data."""
    timestamp: datetime
    alert_type: str  # 'accumulation', 'distribution', 'spike', 'regime_change'
    severity: str    # 'low', 'medium', 'high', 'critical'
    
    # Alert details
    whale_volume_btc: Decimal
    whale_count: int
    timeframes_affected: List[str]
    
    # Context
    description: str
    confidence_score: Decimal
    
    # Related data
    detection_result: WhaleDetectionResult