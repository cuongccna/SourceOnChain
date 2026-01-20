"""Configuration for OnChain Signal Engine."""

from typing import Dict, List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class SignalEngineConfig(BaseSettings):
    """Configuration for the OnChain Signal Engine."""
    
    # Database Settings
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="bitcoin_signals", description="Database name")
    db_user: str = Field(description="Database username")
    db_password: str = Field(description="Database password")
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_max_overflow: int = Field(default=20, description="Max pool overflow")
    
    # Signal Calculation Settings
    timeframes: List[str] = Field(default=['1h', '4h', '1d'], description="Supported timeframes")
    baseline_lookback_periods: int = Field(default=30, description="Periods for baseline calculation")
    
    # Component Weights (must sum to 1.0)
    component_weights: Dict[str, float] = Field(
        default={
            'network_health': 0.30,
            'capital_flow': 0.30,
            'smart_money': 0.40
        },
        description="Component weights for OnChain score calculation"
    )
    
    # Signal Weights within Components
    signal_weights: Dict[str, Dict[str, float]] = Field(
        default={
            'network_health': {
                'network_growth_signal': 0.6,
                'network_congestion_signal': 0.4
            },
            'capital_flow': {
                'net_utxo_inflow_signal': 0.5,
                'whale_flow_dominance_signal': 0.5
            },
            'smart_money': {
                'smart_money_accumulation_signal': 0.5,
                'smart_money_distribution_signal': 0.5
            },
            'risk_adjustment': {
                'abnormal_activity_signal': 0.5,
                'capital_concentration_signal': 0.5
            }
        },
        description="Signal weights within each component"
    )
    
    # Threshold Configuration
    threshold_config: Dict[str, Dict[str, float]] = Field(
        default={
            'network_growth_signal': {
                'active_addresses_threshold_percentile': 75.0,
                'tx_count_threshold_percentile': 75.0,
                'new_addresses_threshold_percentile': 75.0
            },
            'network_congestion_signal': {
                'fee_threshold_percentile': 90.0,
                'time_threshold_percentile': 90.0,
                'mempool_threshold_percentile': 85.0
            },
            'net_utxo_inflow_signal': {
                'flow_threshold_percentile': 70.0,
                'creation_rate_threshold': 1.1
            },
            'whale_flow_dominance_signal': {
                'volume_dominance_threshold': 0.4,
                'count_dominance_threshold': 0.15
            },
            'smart_money_accumulation_signal': {
                'accumulation_threshold_percentile': 60.0,
                'volume_threshold_percentile': 70.0,
                'address_threshold_percentile': 65.0
            },
            'smart_money_distribution_signal': {
                'flow_threshold_percentile': 40.0,
                'spending_threshold_percentile': 75.0,
                'holding_threshold_percentile': 30.0
            },
            'abnormal_activity_signal': {
                'lower_percentile': 5.0,
                'upper_percentile': 95.0,
                'zscore_threshold': 3.0
            },
            'capital_concentration_signal': {
                'concentration_threshold': 0.7,
                'whale_count_percentile': 90.0,
                'gini_percentile': 85.0
            }
        },
        description="Threshold parameters for each signal"
    )
    
    # Confidence Calculation Settings
    confidence_weights: Dict[str, float] = Field(
        default={
            'signal_agreement': 0.40,
            'historical_stability': 0.30,
            'data_quality': 0.20,
            'statistical_significance': 0.10
        },
        description="Weights for confidence calculation factors"
    )
    
    # Risk Management
    max_risk_penalty: float = Field(default=20.0, description="Maximum risk penalty points")
    risk_penalty_discount_factor: float = Field(default=0.7, description="Discount factor for multiple risk signals")
    
    # Bias Classification Thresholds
    bias_thresholds: Dict[str, float] = Field(
        default={
            'positive_score_threshold': 60.0,
            'negative_score_threshold': 40.0,
            'confidence_threshold': 0.6
        },
        description="Thresholds for bias classification"
    )
    
    # Data Quality Requirements
    min_data_completeness: float = Field(default=0.8, description="Minimum data completeness ratio")
    min_sample_size: int = Field(default=10, description="Minimum sample size for calculations")
    max_calculation_age_hours: int = Field(default=2, description="Maximum age of calculations to use")
    
    # Performance Settings
    calculation_timeout_seconds: int = Field(default=30, description="Timeout for signal calculations")
    enable_parallel_processing: bool = Field(default=True, description="Enable parallel signal processing")
    max_workers: int = Field(default=4, description="Maximum worker threads")
    
    # Caching Settings
    enable_baseline_caching: bool = Field(default=True, description="Enable baseline caching")
    baseline_cache_ttl_hours: int = Field(default=6, description="Baseline cache TTL in hours")
    enable_signal_caching: bool = Field(default=True, description="Enable signal result caching")
    signal_cache_ttl_minutes: int = Field(default=15, description="Signal cache TTL in minutes")
    
    # Verification Settings
    enable_verification: bool = Field(default=True, description="Enable signal verification")
    verification_sample_rate: float = Field(default=0.1, description="Rate of calculations to verify")
    determinism_tolerance: float = Field(default=1e-6, description="Tolerance for determinism tests")
    stability_tolerance: float = Field(default=0.05, description="Tolerance for stability tests")
    
    # Anomaly Detection
    enable_anomaly_detection: bool = Field(default=True, description="Enable anomaly detection")
    confidence_drop_threshold: float = Field(default=0.3, description="Threshold for confidence drop anomalies")
    confidence_drop_ratio: float = Field(default=0.5, description="Ratio for confidence drop detection")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default="logs/signal_engine.log", description="Log file path")
    
    # Monitoring Settings
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9094, description="Metrics server port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "SIGNAL_"
        
    @validator('component_weights')
    def validate_component_weights(cls, v):
        """Validate that component weights sum to 1.0."""
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Component weights must sum to 1.0, got {total}")
        return v
    
    @validator('confidence_weights')
    def validate_confidence_weights(cls, v):
        """Validate that confidence weights sum to 1.0."""
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Confidence weights must sum to 1.0, got {total}")
        return v
    
    @validator('signal_weights')
    def validate_signal_weights(cls, v):
        """Validate that signal weights within each component sum to 1.0."""
        for component, weights in v.items():
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Signal weights for {component} must sum to 1.0, got {total}")
        return v
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_signal_threshold_config(self, signal_id: str) -> Dict[str, float]:
        """Get threshold configuration for a specific signal."""
        return self.threshold_config.get(signal_id, {})
    
    def get_component_signal_weights(self, component: str) -> Dict[str, float]:
        """Get signal weights for a specific component."""
        return self.signal_weights.get(component, {})
    
    def validate_configuration(self) -> bool:
        """Validate the complete configuration."""
        try:
            # Check that all required signals have threshold configs
            required_signals = [
                'network_growth_signal', 'network_congestion_signal',
                'net_utxo_inflow_signal', 'whale_flow_dominance_signal',
                'smart_money_accumulation_signal', 'smart_money_distribution_signal',
                'abnormal_activity_signal', 'capital_concentration_signal'
            ]
            
            for signal_id in required_signals:
                if signal_id not in self.threshold_config:
                    raise ValueError(f"Missing threshold config for {signal_id}")
            
            # Check that all components have signal weights
            for component in self.component_weights.keys():
                if component not in self.signal_weights:
                    raise ValueError(f"Missing signal weights for component {component}")
            
            return True
            
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def get_enabled_signals(self) -> List[str]:
        """Get list of all enabled signal IDs."""
        signals = []
        for component_signals in self.signal_weights.values():
            signals.extend(component_signals.keys())
        return list(set(signals))  # Remove duplicates