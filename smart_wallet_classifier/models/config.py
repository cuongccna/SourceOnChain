"""Configuration for smart wallet classification pipeline."""

from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class SmartWalletConfig(BaseSettings):
    """Configuration for the smart wallet classification engine."""
    
    # Database Settings
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="bitcoin_data", description="Database name")
    db_user: str = Field(description="Database username")
    db_password: str = Field(description="Database password")
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_max_overflow: int = Field(default=20, description="Max pool overflow")
    
    # Classification Settings
    timeframes: List[str] = Field(default=['30d', '90d', '1y'], description="Analysis timeframes")
    
    # Feature Calculation Settings
    min_transaction_count: int = Field(default=10, description="Minimum transactions for classification")
    min_active_days: int = Field(default=30, description="Minimum active days for classification")
    dormancy_threshold_days: int = Field(default=180, description="Days to consider UTXO dormant")
    
    # Classification Thresholds
    smart_money_threshold: float = Field(default=0.70, description="Smart money classification threshold")
    neutral_upper_threshold: float = Field(default=0.60, description="Neutral capital upper threshold")
    neutral_lower_threshold: float = Field(default=0.40, description="Neutral capital lower threshold")
    dumb_money_threshold: float = Field(default=0.30, description="Dumb money classification threshold")
    
    # Smart Money Requirements
    smart_money_min_pnl_score: float = Field(default=0.60, description="Minimum PnL score for smart money")
    smart_money_min_win_rate: float = Field(default=0.55, description="Minimum win rate for smart money")
    smart_money_min_transactions: int = Field(default=20, description="Minimum transactions for smart money")
    smart_money_min_holding_score: float = Field(default=0.50, description="Minimum holding score for smart money")
    
    # Feature Weights
    feature_weights: Dict[str, float] = Field(
        default={
            'holding_behavior': 0.25,
            'pnl_efficiency': 0.35,
            'timing_quality': 0.25,
            'activity_discipline': 0.15
        },
        description="Feature weights for composite score calculation"
    )
    
    # Noise Filtering Thresholds
    max_inputs_per_tx: int = Field(default=50, description="Max inputs per tx (exchange filter)")
    max_outputs_per_tx: int = Field(default=20, description="Max outputs per tx (exchange filter)")
    max_coinbase_ratio: float = Field(default=0.8, description="Max coinbase ratio (mining filter)")
    min_avg_tx_value: float = Field(default=0.001, description="Min average tx value BTC (dust filter)")
    max_round_number_ratio: float = Field(default=0.7, description="Max round number ratio (exchange filter)")
    
    # Statistical Validation
    min_effect_size: float = Field(default=0.1, description="Minimum effect size for significance")
    min_confidence_score: float = Field(default=0.05, description="Minimum confidence score")
    max_confidence_score: float = Field(default=0.95, description="Maximum confidence score")
    
    # Performance Settings
    batch_size: int = Field(default=1000, description="Batch size for processing addresses")
    enable_parallel_processing: bool = Field(default=True, description="Enable parallel processing")
    max_workers: int = Field(default=4, description="Maximum worker threads")
    
    # Caching Settings
    enable_feature_caching: bool = Field(default=True, description="Enable feature caching")
    feature_cache_ttl_hours: int = Field(default=24, description="Feature cache TTL in hours")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default="logs/smart_wallet_classifier.log", description="Log file path")
    
    # Monitoring Settings
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9093, description="Metrics server port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "WALLET_"
        
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_smart_money_requirements(self) -> Dict[str, float]:
        """Get smart money classification requirements."""
        return {
            'min_pnl_score': self.smart_money_min_pnl_score,
            'min_win_rate': self.smart_money_min_win_rate,
            'min_transactions': self.smart_money_min_transactions,
            'min_holding_score': self.smart_money_min_holding_score
        }
    
    def get_noise_filtering_criteria(self) -> Dict[str, float]:
        """Get noise filtering criteria."""
        return {
            'max_inputs_per_tx': self.max_inputs_per_tx,
            'max_outputs_per_tx': self.max_outputs_per_tx,
            'max_coinbase_ratio': self.max_coinbase_ratio,
            'min_avg_tx_value': self.min_avg_tx_value,
            'max_round_number_ratio': self.max_round_number_ratio
        }
    
    def validate_feature_weights(self) -> bool:
        """Validate that feature weights sum to 1.0."""
        total_weight = sum(self.feature_weights.values())
        return abs(total_weight - 1.0) < 0.001
    
    def validate_thresholds(self) -> bool:
        """Validate threshold configuration."""
        return (
            self.dumb_money_threshold < self.neutral_lower_threshold < 
            self.neutral_upper_threshold < self.smart_money_threshold
        )