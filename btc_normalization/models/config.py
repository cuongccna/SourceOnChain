"""Configuration for Bitcoin normalization pipeline."""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class NormalizationConfig(BaseSettings):
    """Configuration for the Bitcoin normalization pipeline."""
    
    # Database Settings (inherits from collector)
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="bitcoin_data", description="Database name")
    db_user: str = Field(description="Database username")
    db_password: str = Field(description="Database password")
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_max_overflow: int = Field(default=20, description="Max pool overflow")
    
    # Normalization Settings
    timeframes: List[str] = Field(default=['1h', '4h', '1d'], description="Timeframes to normalize")
    batch_size_hours: int = Field(default=24, description="Hours to process in each batch")
    lookback_window_hours: int = Field(default=720, description="Lookback window for percentile calculations (30 days)")
    
    # Statistical Settings
    large_tx_percentile: float = Field(default=95.0, description="Percentile threshold for large transactions")
    whale_tx_percentile: float = Field(default=99.9, description="Percentile threshold for whale transactions")
    dormancy_threshold_days: int = Field(default=30, description="Days of inactivity to consider address dormant")
    
    # Performance Settings
    enable_parallel_processing: bool = Field(default=True, description="Enable parallel timeframe processing")
    max_workers: int = Field(default=4, description="Maximum worker threads")
    chunk_size: int = Field(default=10000, description="Database query chunk size")
    
    # Caching Settings
    enable_threshold_caching: bool = Field(default=True, description="Cache percentile calculations")
    threshold_cache_ttl_hours: int = Field(default=6, description="Threshold cache TTL in hours")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default="logs/btc_normalization.log", description="Log file path")
    
    # Monitoring Settings
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9091, description="Metrics server port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "NORM_"
        
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def validate_timeframes(self) -> bool:
        """Validate timeframe configuration."""
        valid_timeframes = {'1h', '4h', '1d'}
        return all(tf in valid_timeframes for tf in self.timeframes)
    
    def get_timeframe_seconds(self, timeframe: str) -> int:
        """Get timeframe duration in seconds."""
        timeframe_map = {
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        return timeframe_map.get(timeframe, 3600)