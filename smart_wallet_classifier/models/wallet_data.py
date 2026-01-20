"""Data models for wallet classification results."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class WalletBehaviorFeatures:
    """Wallet behavioral features extracted from on-chain data."""
    address: str
    timeframe: str
    calculation_timestamp: datetime
    
    # Data quality metrics
    transaction_count: int
    active_days: int
    first_tx_date: datetime
    last_tx_date: datetime
    
    # 1. Holding Behavior Features
    avg_utxo_holding_time_days: Decimal
    holding_time_p25_days: Decimal = Decimal('0')
    holding_time_p50_days: Decimal = Decimal('0')
    holding_time_p75_days: Decimal = Decimal('0')
    holding_time_p90_days: Decimal = Decimal('0')
    dormancy_activation_rate: Decimal = Decimal('0')
    
    # 2. Capital Efficiency Features (PnL Proxy)
    realized_profit_btc: Decimal = Decimal('0')
    realized_loss_btc: Decimal = Decimal('0')
    net_realized_pnl_btc: Decimal = Decimal('0')
    profit_loss_ratio: Decimal = Decimal('0')
    win_rate: Decimal = Decimal('0')
    profitable_spends: int = 0
    total_spends: int = 0
    
    # 3. Timing Quality Features
    accumulation_before_whale_spike_rate: Decimal = Decimal('0')
    distribution_after_whale_spike_rate: Decimal = Decimal('0')
    accumulation_periods_count: int = 0
    distribution_periods_count: int = 0
    successful_accumulations: int = 0
    successful_distributions: int = 0
    
    # 4. Activity Discipline Features
    tx_frequency_per_day: Decimal = Decimal('0')
    tx_frequency_std: Decimal = Decimal('0')
    burst_vs_consistency_score: Decimal = Decimal('0')
    overtrading_penalty: Decimal = Decimal('0')
    avg_tx_interval_hours: Decimal = Decimal('0')
    
    # Network-relative percentiles (0-1 scale)
    avg_holding_time_percentile: Decimal = Decimal('0')
    win_rate_percentile: Decimal = Decimal('0')
    profit_loss_ratio_percentile: Decimal = Decimal('0')
    net_pnl_percentile: Decimal = Decimal('0')
    tx_frequency_std_percentile: Decimal = Decimal('0')
    
    # Additional behavioral metrics
    round_number_tx_ratio: Decimal = Decimal('0')
    coinbase_tx_ratio: Decimal = Decimal('0')
    avg_inputs_per_tx: Decimal = Decimal('0')
    avg_outputs_per_tx: Decimal = Decimal('0')
    avg_tx_value_btc: Decimal = Decimal('0')


@dataclass
class WalletClassification:
    """Wallet classification result."""
    address: str
    timeframe: str
    calculation_timestamp: datetime
    
    # Classification results
    class_label: str  # 'SMART_MONEY', 'NEUTRAL_CAPITAL', 'DUMB_MONEY', 'NOISE'
    confidence_score: Decimal
    
    # Composite scores (0-1 scale)
    holding_behavior_score: Decimal
    pnl_efficiency_score: Decimal
    timing_quality_score: Decimal
    activity_discipline_score: Decimal
    overall_smart_money_score: Decimal
    
    # Feature contributions
    holding_contribution: Decimal = Decimal('0')
    pnl_contribution: Decimal = Decimal('0')
    timing_contribution: Decimal = Decimal('0')
    discipline_contribution: Decimal = Decimal('0')
    
    # Classification metadata
    meets_smart_money_requirements: bool = False
    meets_dumb_money_criteria: bool = False
    excluded_as_noise: bool = False
    exclusion_reason: Optional[str] = None
    
    # Statistical validation
    classification_significant: bool = False
    effect_size_vs_network: Decimal = Decimal('0')
    sample_size_adequate: bool = False
    
    # Multi-timeframe consistency
    consistency_score: Optional[Decimal] = None
    majority_vote_classification: Optional[str] = None


@dataclass
class NetworkBehaviorStats:
    """Network-wide behavioral statistics for normalization."""
    calculation_timestamp: datetime
    timeframe: str
    
    # Sample size
    total_addresses_analyzed: int
    addresses_excluded_as_noise: int = 0
    
    # Holding behavior network stats
    network_median_holding_time_days: Decimal
    network_p25_holding_time_days: Decimal = Decimal('0')
    network_p75_holding_time_days: Decimal = Decimal('0')
    
    # PnL efficiency network stats
    network_median_win_rate: Decimal
    network_p25_win_rate: Decimal = Decimal('0')
    network_p75_win_rate: Decimal = Decimal('0')
    network_median_pnl_ratio: Decimal = Decimal('0')
    
    # Activity discipline network stats
    network_median_tx_frequency: Decimal
    network_median_consistency_score: Decimal = Decimal('0')
    
    # Classification distribution
    smart_money_percentage: Decimal = Decimal('0')
    neutral_capital_percentage: Decimal = Decimal('0')
    dumb_money_percentage: Decimal = Decimal('0')
    noise_percentage: Decimal = Decimal('0')
    
    # Quality metrics
    avg_confidence_score: Decimal = Decimal('0')
    classification_consistency_score: Decimal = Decimal('0')


@dataclass
class ClassificationResult:
    """Complete classification result for a wallet."""
    address: str
    timeframe: str
    success: bool
    
    # Feature data
    features: Optional[WalletBehaviorFeatures] = None
    classification: Optional[WalletClassification] = None
    
    # Processing metadata
    processing_time_ms: Optional[int] = None
    transactions_analyzed: Optional[int] = None
    utxos_analyzed: Optional[int] = None
    error_message: Optional[str] = None
    
    # Data quality metrics
    data_completeness: Optional[float] = None
    feature_quality_score: Optional[float] = None


@dataclass
class MultiTimeframeClassification:
    """Classification result across multiple timeframes."""
    address: str
    calculation_timestamp: datetime
    
    # Individual timeframe results
    timeframe_results: Dict[str, ClassificationResult]
    
    # Consensus classification
    final_classification: str
    final_confidence: Decimal
    consistency_score: Decimal
    
    # Cross-timeframe analysis
    classification_stability: Decimal  # How stable across timeframes
    score_variance: Decimal  # Variance in scores across timeframes
    
    # Majority vote details
    classification_votes: Dict[str, int]
    weighted_average_score: Decimal


@dataclass
class WalletClassificationHistory:
    """Historical classification tracking for a wallet."""
    address: str
    timeframe: str
    
    # Historical data
    classification_history: List[WalletClassification]
    
    # Stability metrics
    total_class_changes: int
    days_in_current_class: int
    classification_stability_score: Decimal
    
    # Trend analysis
    score_trend: str  # 'improving', 'declining', 'stable'
    confidence_trend: str
    recent_score_change: Decimal
    recent_confidence_change: Decimal


@dataclass
class SmartMoneyCohort:
    """Smart money cohort definition and tracking."""
    cohort_id: str
    cohort_name: str
    timeframe: str
    creation_timestamp: datetime
    
    # Cohort criteria
    min_confidence_score: Decimal
    min_smart_money_score: Decimal
    min_transaction_count: int
    min_active_days: int
    
    # Cohort statistics
    total_addresses: int
    avg_confidence_score: Decimal = Decimal('0')
    avg_smart_money_score: Decimal = Decimal('0')
    avg_win_rate: Decimal = Decimal('0')
    avg_holding_time_days: Decimal = Decimal('0')
    
    # Performance tracking
    cohort_performance_score: Decimal = Decimal('0')
    cohort_consistency_score: Decimal = Decimal('0')
    
    # Member addresses
    member_addresses: List[str]


@dataclass
class ClassificationExplanation:
    """Detailed explanation of classification decision."""
    address: str
    timeframe: str
    classification: str
    confidence: Decimal
    
    # Feature breakdown
    feature_scores: Dict[str, Decimal]
    feature_percentiles: Dict[str, Decimal]
    feature_contributions: Dict[str, Decimal]
    
    # Decision factors
    key_positive_factors: List[str]
    key_negative_factors: List[str]
    threshold_distances: Dict[str, Decimal]
    
    # Comparison to network
    vs_network_median: Dict[str, Decimal]
    vs_smart_money_cohort: Dict[str, Decimal]
    vs_dumb_money_cohort: Dict[str, Decimal]
    
    # Explanation text
    summary_explanation: str
    detailed_reasoning: List[str]