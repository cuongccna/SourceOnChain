"""Configuration for whale detection pipeline."""

from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class WhaleDetectionConfig(BaseSettings):
    """Configuration for the whale detection engine."""
    
    # Database Settings (inherits from normalization layer)
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="bitcoin_data", description="Database name")
    db_user: str = Field(description="Database username")
    db_password: str = Field(description="Database password")
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_max_overflow: int = Field(default=20, description="Max pool overflow")
    
    # Whale Detection Settings
    timeframes: List[str] = Field(default=['1h', '4h', '1d'], description="Timeframes to analyze")
    
    # Percentile Thresholds
    large_tx_percentile: float = Field(default=95.0, description="Large transaction percentile (P95)")
    whale_tx_percentile: float = Field(default=99.0, description="Whale transaction percentile (P99)")
    ultra_whale_percentile: float = Field(default=99.9, description="Ultra-whale percentile (P99.9)")
    leviathan_percentile: float = Field(default=99.99, description="Leviathan percentile (P99.99)")
    
    # Rolling Window Settings
    rolling_windows: Dict[str, int] = Field(
        default={
            '1h': 168,  # 7 days of hourly data
            '4h': 180,  # 30 days of 4-hour data
            '1d': 90,   # 90 days of daily data
        },
        description="Rolling window sizes for threshold calculation"
    )
    
    # Activity Spike Detection
    activity_spike_zscore_threshold: float = Field(default=2.0, description="Z-score threshold for activity spikes")
    volume_spike_zscore_threshold: float = Field(default=2.5, description="Z-score threshold for volume spikes")
    
    # Behavioral Pattern Detection
    accumulation_min_periods: int = Field(default=3, description="Minimum periods for accumulation detection")
    distribution_min_periods: int = Field(default=3, description="Minimum periods for distribution detection")
    trend_strength_threshold: float = Field(default=0.1, description="Minimum trend strength for pattern detection")
    
    # Threshold Caching
    enable_threshold_caching: bool = Field(default=True, description="Enable threshold caching")
    threshold_cache_ttl_hours: int = Field(default=1, description="Threshold cache TTL in hours")
    
    # Statistical Validation
    min_sample_size: int = Field(default=1000, description="Minimum sample size for threshold calculation")
    stability_threshold: float = Field(default=0.3, description="Maximum CV for threshold stability")
    regime_change_sensitivity: float = Field(default=2.0, description="Z-score sensitivity for regime change detection")
    
    # Performance Settings
    batch_size: int = Field(default=100, description="Batch size for processing")
    enable_parallel_processing: bool = Field(default=True, description="Enable parallel processing")
    max_workers: int = Field(default=4, description="Maximum worker threads")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default="logs/whale_detection.log", description="Log file path")
    
    # Monitoring Settings
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9092, description="Metrics server port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "WHALE_"
        
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_rolling_window(self, timeframe: str) -> int:
        """Get rolling window size for timeframe."""
        return self.rolling_windows.get(timeframe, 168)
    
    def validate_percentiles(self) -> bool:
        """Validate percentile configuration."""
        percentiles = [
            self.large_tx_percentile,
            self.whale_tx_percentile, 
            self.ultra_whale_percentile,
            self.leviathan_percentile
        ]
        
        # Check ascending order
        return all(percentiles[i] < percentiles[i+1] for i in range(len(percentiles)-1))
    
    def get_percentile_thresholds(self) -> Dict[str, float]:
        """Get all percentile thresholds as dictionary."""
        return {
            'large': self.large_tx_percentile,
            'whale': self.whale_tx_percentile,
            'ultra_whale': self.ultra_whale_percentile,
            'leviathan': self.leviathan_percentile
        }