"""Configuration management using Pydantic settings."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class CollectorConfig(BaseSettings):
    """Configuration for the Bitcoin data collector."""
    
    # Bitcoin Core RPC Settings
    bitcoin_rpc_host: str = Field(default="localhost", description="Bitcoin Core RPC host")
    bitcoin_rpc_port: int = Field(default=8332, description="Bitcoin Core RPC port")
    bitcoin_rpc_user: str = Field(description="Bitcoin Core RPC username")
    bitcoin_rpc_password: str = Field(description="Bitcoin Core RPC password")
    bitcoin_rpc_timeout: int = Field(default=30, description="RPC timeout in seconds")
    
    # Database Settings
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="bitcoin_data", description="Database name")
    db_user: str = Field(description="Database username")
    db_password: str = Field(description="Database password")
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_max_overflow: int = Field(default=20, description="Max pool overflow")
    
    # Sync Settings
    sync_batch_size: int = Field(default=100, description="Blocks to process in batch")
    sync_start_height: int = Field(default=0, description="Starting block height")
    sync_concurrent_blocks: int = Field(default=5, description="Concurrent block processing")
    sync_retry_attempts: int = Field(default=3, description="Retry attempts for failed operations")
    sync_retry_delay: int = Field(default=5, description="Delay between retries in seconds")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    log_file: Optional[str] = Field(default="logs/btc_collector.log", description="Log file path")
    log_max_size_mb: int = Field(default=100, description="Max log file size in MB")
    log_backup_count: int = Field(default=5, description="Number of log backups")
    
    # Performance Settings
    cache_size_mb: int = Field(default=512, description="Cache size in MB")
    worker_threads: int = Field(default=4, description="Number of worker threads")
    queue_size: int = Field(default=1000, description="Processing queue size")
    
    # Feature Flags
    enable_address_tracking: bool = Field(default=True, description="Enable address aggregation")
    enable_daily_stats: bool = Field(default=True, description="Enable daily statistics")
    enable_mempool_monitoring: bool = Field(default=False, description="Enable mempool monitoring")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @property
    def bitcoin_rpc_url(self) -> str:
        """Generate Bitcoin Core RPC URL."""
        return f"http://{self.bitcoin_rpc_user}:{self.bitcoin_rpc_password}@{self.bitcoin_rpc_host}:{self.bitcoin_rpc_port}"
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"