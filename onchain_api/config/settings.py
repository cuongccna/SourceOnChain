"""Configuration settings for OnChain API."""

from typing import List, Dict, Any, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API configuration settings."""
    
    # API Configuration
    api_title: str = Field(default="OnChain Intelligence API", description="API title")
    api_description: str = Field(default="Production-grade Bitcoin on-chain intelligence API", description="API description")
    api_version: str = Field(default="1.0.0", description="API version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of worker processes")
    
    # Database Configuration
    database_url: str = Field(..., description="Database connection URL")
    db_pool_size: int = Field(default=20, description="Database connection pool size")
    db_max_overflow: int = Field(default=30, description="Database max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Database connection timeout")
    
    # Security Configuration
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    allowed_api_keys: List[str] = Field(default_factory=list, description="Allowed API keys")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    cors_methods: List[str] = Field(default=["GET", "POST"], description="CORS allowed methods")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=1000, description="Requests per hour per API key")
    rate_limit_window: int = Field(default=3600, description="Rate limit window in seconds")
    
    # Kill Switch Configuration
    kill_switch_min_confidence_ok: float = Field(default=0.70, description="Min confidence for OK status")
    kill_switch_min_confidence_degraded: float = Field(default=0.50, description="Min confidence for DEGRADED status")
    kill_switch_min_confidence_blocked: float = Field(default=0.30, description="Min confidence before BLOCKED")
    
    kill_switch_min_data_completeness_ok: float = Field(default=0.90, description="Min data completeness for OK")
    kill_switch_min_data_completeness_degraded: float = Field(default=0.70, description="Min data completeness for DEGRADED")
    kill_switch_min_data_completeness_blocked: float = Field(default=0.50, description="Min data completeness before BLOCKED")
    
    kill_switch_max_pipeline_lag_ok: int = Field(default=3, description="Max pipeline lag blocks for OK")
    kill_switch_max_pipeline_lag_degraded: int = Field(default=10, description="Max pipeline lag blocks for DEGRADED")
    kill_switch_max_pipeline_lag_blocked: int = Field(default=50, description="Max pipeline lag blocks before BLOCKED")
    
    kill_switch_max_conflicting_signals_ok: int = Field(default=1, description="Max conflicting signals for OK")
    kill_switch_max_conflicting_signals_degraded: int = Field(default=3, description="Max conflicting signals for DEGRADED")
    kill_switch_max_conflicting_signals_blocked: int = Field(default=5, description="Max conflicting signals before BLOCKED")
    
    # Caching Configuration
    enable_response_caching: bool = Field(default=True, description="Enable response caching")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    cache_max_size: int = Field(default=1000, description="Maximum cache entries")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    access_log: bool = Field(default=True, description="Enable access logging")
    
    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")
    enable_health_checks: bool = Field(default=True, description="Enable health check endpoints")
    
    # Signal Engine Configuration
    signal_engine_timeout: int = Field(default=30, description="Signal calculation timeout in seconds")
    signal_engine_retry_attempts: int = Field(default=3, description="Signal calculation retry attempts")
    signal_engine_retry_delay: float = Field(default=1.0, description="Retry delay in seconds")
    
    # Audit Configuration
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")
    audit_log_file: Optional[str] = Field(default="logs/audit.log", description="Audit log file")
    audit_retention_days: int = Field(default=90, description="Audit log retention in days")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "ONCHAIN_API_"
    
    @validator('allowed_api_keys')
    def validate_api_keys(cls, v):
        """Validate API keys are provided in production."""
        if not v:
            raise ValueError("At least one API key must be configured")
        return v
    
    @validator('kill_switch_min_confidence_ok', 'kill_switch_min_confidence_degraded', 'kill_switch_min_confidence_blocked')
    def validate_confidence_thresholds(cls, v):
        """Validate confidence thresholds are in valid range."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence thresholds must be between 0 and 1")
        return v
    
    def get_kill_switch_config(self) -> Dict[str, Any]:
        """Get kill switch configuration dictionary."""
        return {
            'min_confidence_ok': self.kill_switch_min_confidence_ok,
            'min_confidence_degraded': self.kill_switch_min_confidence_degraded,
            'min_confidence_blocked': self.kill_switch_min_confidence_blocked,
            'min_data_completeness_ok': self.kill_switch_min_data_completeness_ok,
            'min_data_completeness_degraded': self.kill_switch_min_data_completeness_degraded,
            'min_data_completeness_blocked': self.kill_switch_min_data_completeness_blocked,
            'max_pipeline_lag_ok': self.kill_switch_max_pipeline_lag_ok,
            'max_pipeline_lag_degraded': self.kill_switch_max_pipeline_lag_degraded,
            'max_pipeline_lag_blocked': self.kill_switch_max_pipeline_lag_blocked,
            'max_conflicting_signals_ok': self.kill_switch_max_conflicting_signals_ok,
            'max_conflicting_signals_degraded': self.kill_switch_max_conflicting_signals_degraded,
            'max_conflicting_signals_blocked': self.kill_switch_max_conflicting_signals_blocked
        }