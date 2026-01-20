"""Data models for signal engine results."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    """Signal type enumeration."""
    BINARY = "binary"
    CATEGORICAL = "categorical"
    INTENSITY = "intensity"


class SignalCategory(Enum):
    """Signal category enumeration."""
    NETWORK_HEALTH = "network_health"
    CAPITAL_FLOW = "capital_flow"
    SMART_MONEY = "smart_money"
    RISK = "risk"


class BiasType(Enum):
    """Bias classification enumeration."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class SignalResult:
    """Individual signal calculation result."""
    signal_id: str
    signal_name: str
    signal_category: SignalCategory
    signal_type: SignalType
    
    # Core result
    value: bool  # For binary signals
    confidence: Decimal
    
    # Calculation metadata
    timestamp: datetime
    asset: str = "BTC"
    timeframe: str = "1d"
    
    # Threshold information
    threshold_values: Dict[str, float] = field(default_factory=dict)
    baseline_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Quality metrics
    data_quality_score: Decimal = Decimal('1.0')
    statistical_significance: Decimal = Decimal('0.0')
    calculation_time_ms: int = 0
    
    # Verification data
    input_data_hash: str = ""
    reproducible: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'signal_id': self.signal_id,
            'signal_name': self.signal_name,
            'signal_category': self.signal_category.value,
            'signal_type': self.signal_type.value,
            'value': self.value,
            'confidence': float(self.confidence),
            'timestamp': self.timestamp.isoformat(),
            'asset': self.asset,
            'timeframe': self.timeframe,
            'threshold_values': self.threshold_values,
            'baseline_metrics': self.baseline_metrics,
            'data_quality_score': float(self.data_quality_score),
            'statistical_significance': float(self.statistical_significance),
            'calculation_time_ms': self.calculation_time_ms,
            'input_data_hash': self.input_data_hash,
            'reproducible': self.reproducible
        }


@dataclass
class ComponentScore:
    """Component score breakdown."""
    component_name: str
    score: Decimal  # 0-100 scale
    confidence: Decimal  # 0-1 scale
    
    # Contributing signals
    signal_results: List[SignalResult] = field(default_factory=list)
    signal_contributions: Dict[str, Decimal] = field(default_factory=dict)
    
    # Metadata
    calculation_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'component_name': self.component_name,
            'score': float(self.score),
            'confidence': float(self.confidence),
            'signal_contributions': {k: float(v) for k, v in self.signal_contributions.items()},
            'calculation_time_ms': self.calculation_time_ms
        }


@dataclass
class ConfidenceBreakdown:
    """Confidence score breakdown."""
    overall_confidence: Decimal
    
    # Factor contributions
    signal_agreement: Decimal = Decimal('0.0')
    historical_stability: Decimal = Decimal('0.0')
    data_quality: Decimal = Decimal('0.0')
    statistical_significance: Decimal = Decimal('0.0')
    
    # Weights used
    confidence_weights: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'overall_confidence': float(self.overall_confidence),
            'signal_agreement': float(self.signal_agreement),
            'historical_stability': float(self.historical_stability),
            'data_quality': float(self.data_quality),
            'statistical_significance': float(self.statistical_significance),
            'confidence_weights': self.confidence_weights
        }


@dataclass
class OnChainScore:
    """Complete OnChain score result."""
    # Core results
    asset: str
    timeframe: str
    timestamp: datetime
    onchain_score: Decimal  # 0-100 scale
    confidence: Decimal  # 0-1 scale
    bias: BiasType
    
    # Component breakdown
    network_health_score: ComponentScore
    capital_flow_score: ComponentScore
    smart_money_score: ComponentScore
    risk_penalty: Decimal = Decimal('0.0')
    
    # All signal results
    signals: Dict[str, SignalResult] = field(default_factory=dict)
    
    # Confidence breakdown
    confidence_breakdown: ConfidenceBreakdown = field(default_factory=lambda: ConfidenceBreakdown(Decimal('0.0')))
    
    # Verification data
    input_data_hash: str = ""
    calculation_hash: str = ""
    reproducible: bool = True
    
    # Metadata
    signal_count: int = 0
    active_signals: int = 0
    conflicting_signals: int = 0
    calculation_time_ms: int = 0
    data_completeness: Decimal = Decimal('1.0')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (OUTPUT CONTRACT)."""
        return {
            'asset': self.asset,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat(),
            'onchain_score': float(self.onchain_score),
            'confidence': float(self.confidence),
            'bias': self.bias.value,
            'signals': {k: v.to_dict() for k, v in self.signals.items()},
            'components': {
                'network_health': self.network_health_score.to_dict(),
                'capital_flow': self.capital_flow_score.to_dict(),
                'smart_money': self.smart_money_score.to_dict(),
                'risk_penalty': float(self.risk_penalty)
            },
            'verification': {
                'input_data_hash': self.input_data_hash,
                'calculation_hash': self.calculation_hash,
                'reproducible': self.reproducible,
                'signal_count': self.signal_count,
                'active_signals': self.active_signals,
                'conflicting_signals': self.conflicting_signals,
                'calculation_time_ms': self.calculation_time_ms,
                'data_completeness': float(self.data_completeness)
            }
        }
    
    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of signal states."""
        summary = {
            'total_signals': len(self.signals),
            'active_signals': sum(1 for s in self.signals.values() if s.value),
            'by_category': {},
            'avg_confidence': 0.0,
            'min_confidence': 1.0,
            'max_confidence': 0.0
        }
        
        # Group by category
        for signal in self.signals.values():
            category = signal.signal_category.value
            if category not in summary['by_category']:
                summary['by_category'][category] = {'total': 0, 'active': 0, 'avg_confidence': 0.0}
            
            summary['by_category'][category]['total'] += 1
            if signal.value:
                summary['by_category'][category]['active'] += 1
        
        # Calculate confidence statistics
        if self.signals:
            confidences = [float(s.confidence) for s in self.signals.values()]
            summary['avg_confidence'] = sum(confidences) / len(confidences)
            summary['min_confidence'] = min(confidences)
            summary['max_confidence'] = max(confidences)
            
            # Category confidence averages
            for category in summary['by_category']:
                category_confidences = [
                    float(s.confidence) for s in self.signals.values()
                    if s.signal_category.value == category
                ]
                if category_confidences:
                    summary['by_category'][category]['avg_confidence'] = sum(category_confidences) / len(category_confidences)
        
        return summary


@dataclass
class SignalBaseline:
    """Baseline statistics for signal calculation."""
    signal_id: str
    asset: str
    timeframe: str
    calculation_timestamp: datetime
    
    # Baseline period
    baseline_start_timestamp: datetime
    baseline_end_timestamp: datetime
    baseline_period_days: int
    
    # Statistical baselines
    baseline_mean: Decimal = Decimal('0.0')
    baseline_median: Decimal = Decimal('0.0')
    baseline_std_dev: Decimal = Decimal('0.0')
    baseline_min: Decimal = Decimal('0.0')
    baseline_max: Decimal = Decimal('0.0')
    
    # Percentile thresholds
    p5_threshold: Decimal = Decimal('0.0')
    p10_threshold: Decimal = Decimal('0.0')
    p25_threshold: Decimal = Decimal('0.0')
    p75_threshold: Decimal = Decimal('0.0')
    p90_threshold: Decimal = Decimal('0.0')
    p95_threshold: Decimal = Decimal('0.0')
    
    # Dynamic threshold (calculated)
    current_threshold: Decimal = Decimal('0.0')
    threshold_type: str = "percentile"
    
    # Quality metrics
    sample_size: int = 0
    data_completeness: Decimal = Decimal('1.0')
    outlier_count: int = 0
    
    def get_percentile_threshold(self, percentile: float) -> Decimal:
        """Get threshold for specific percentile."""
        percentile_map = {
            5: self.p5_threshold,
            10: self.p10_threshold,
            25: self.p25_threshold,
            75: self.p75_threshold,
            90: self.p90_threshold,
            95: self.p95_threshold
        }
        return percentile_map.get(percentile, self.baseline_median)


@dataclass
class SignalAnomaly:
    """Signal anomaly detection result."""
    anomaly_id: str
    asset: str
    timeframe: str
    timestamp: datetime
    
    # Anomaly details
    anomaly_type: str  # 'threshold_breach', 'confidence_drop', 'calculation_error', 'data_quality'
    severity: str  # 'low', 'medium', 'high', 'critical'
    
    # Affected signals
    affected_signals: List[str] = field(default_factory=list)
    primary_signal_id: Optional[str] = None
    
    # Anomaly metrics
    anomaly_score: Decimal = Decimal('0.0')  # 0-1 scale
    deviation_magnitude: Decimal = Decimal('0.0')
    confidence_impact: Decimal = Decimal('0.0')
    
    # Context
    description: str = ""
    probable_cause: str = ""
    recommended_action: str = ""
    
    # Resolution tracking
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: str = ""


@dataclass
class VerificationResult:
    """Signal verification test result."""
    verification_type: str  # 'invariant', 'determinism', 'stability', 'time_shift'
    test_name: str
    verification_passed: bool
    verification_score: Decimal = Decimal('0.0')
    
    # Test details
    expected_result: Dict[str, Any] = field(default_factory=dict)
    actual_result: Dict[str, Any] = field(default_factory=dict)
    deviation_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Error details (if failed)
    error_message: str = ""
    error_code: str = ""
    
    # Performance
    verification_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'verification_type': self.verification_type,
            'test_name': self.test_name,
            'verification_passed': self.verification_passed,
            'verification_score': float(self.verification_score),
            'expected_result': self.expected_result,
            'actual_result': self.actual_result,
            'deviation_metrics': self.deviation_metrics,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'verification_time_ms': self.verification_time_ms
        }


@dataclass
class SignalEngineStatus:
    """Overall signal engine status."""
    timestamp: datetime
    engine_version: str
    
    # Health metrics
    total_signals_configured: int = 0
    active_signals: int = 0
    failed_signals: int = 0
    
    # Performance metrics
    avg_calculation_time_ms: float = 0.0
    max_calculation_time_ms: int = 0
    calculations_per_minute: float = 0.0
    
    # Quality metrics
    avg_confidence_score: float = 0.0
    avg_data_quality: float = 0.0
    anomaly_count_last_hour: int = 0
    
    # System metrics
    database_connection_healthy: bool = True
    cache_hit_rate: float = 0.0
    memory_usage_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'engine_version': self.engine_version,
            'health_metrics': {
                'total_signals_configured': self.total_signals_configured,
                'active_signals': self.active_signals,
                'failed_signals': self.failed_signals
            },
            'performance_metrics': {
                'avg_calculation_time_ms': self.avg_calculation_time_ms,
                'max_calculation_time_ms': self.max_calculation_time_ms,
                'calculations_per_minute': self.calculations_per_minute
            },
            'quality_metrics': {
                'avg_confidence_score': self.avg_confidence_score,
                'avg_data_quality': self.avg_data_quality,
                'anomaly_count_last_hour': self.anomaly_count_last_hour
            },
            'system_metrics': {
                'database_connection_healthy': self.database_connection_healthy,
                'cache_hit_rate': self.cache_hit_rate,
                'memory_usage_mb': self.memory_usage_mb
            }
        }