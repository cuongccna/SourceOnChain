"""
Data Source Configuration for OnChain Collector.

Supports multiple data sources:
- Bitcoin Core RPC (requires local node)
- Blockchain.info API (free, no node required)
- Mempool.space API (better for mempool data)
- BlockCypher API (more features)
"""

import os
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class DataSourceConfig(BaseSettings):
    """Configuration for blockchain data source."""
    
    # Data source selection
    data_source: Literal["rpc", "blockchain_info", "mempool_space", "blockcypher"] = Field(
        default="blockchain_info",
        description="Data source to use for blockchain data"
    )
    
    # ==================== Blockchain.info Settings ====================
    blockchain_info_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for higher rate limits"
    )
    blockchain_info_rate_limit: float = Field(
        default=1.0,
        description="Delay between requests in seconds"
    )
    
    # ==================== Mempool.space Settings ====================
    mempool_space_url: str = Field(
        default="https://mempool.space/api",
        description="Mempool.space API base URL"
    )
    
    # ==================== BlockCypher Settings ====================
    blockcypher_api_token: Optional[str] = Field(
        default=None,
        description="BlockCypher API token for higher rate limits"
    )
    
    # ==================== Bitcoin Core RPC Settings ====================
    bitcoin_rpc_host: str = Field(
        default="localhost",
        description="Bitcoin Core RPC host"
    )
    bitcoin_rpc_port: int = Field(
        default=8332,
        description="Bitcoin Core RPC port"
    )
    bitcoin_rpc_user: str = Field(
        default="",
        description="Bitcoin Core RPC username"
    )
    bitcoin_rpc_password: str = Field(
        default="",
        description="Bitcoin Core RPC password"
    )
    bitcoin_rpc_timeout: int = Field(
        default=30,
        description="RPC timeout in seconds"
    )
    
    # ==================== Common Settings ====================
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests"
    )
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    
    # ==================== Database Settings ====================
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="bitcoin_onchain_signals")
    db_user: str = Field(default="onchain_user")
    db_password: str = Field(default="onchain_pass")
    
    # ==================== Sync Settings ====================
    sync_batch_size: int = Field(default=10, description="Blocks to process in batch")
    sync_start_height: int = Field(default=0, description="Starting block height")
    sync_retry_attempts: int = Field(default=3)
    sync_retry_delay: int = Field(default=5)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_source_info(self) -> dict:
        """Get information about the configured data source."""
        info = {
            "source": self.data_source,
            "requires_node": self.data_source == "rpc",
        }
        
        if self.data_source == "blockchain_info":
            info["api_url"] = "https://blockchain.info"
            info["has_api_key"] = bool(self.blockchain_info_api_key)
            info["rate_limit"] = f"{self.blockchain_info_rate_limit}s between requests"
            
        elif self.data_source == "mempool_space":
            info["api_url"] = self.mempool_space_url
            
        elif self.data_source == "blockcypher":
            info["api_url"] = "https://api.blockcypher.com/v1/btc/main"
            info["has_api_key"] = bool(self.blockcypher_api_token)
            
        elif self.data_source == "rpc":
            info["rpc_host"] = self.bitcoin_rpc_host
            info["rpc_port"] = self.bitcoin_rpc_port
            
        return info
