"""
Unified Data Provider for Bitcoin blockchain data.

Abstract away the data source (RPC vs Public APIs).
Switch between sources via configuration without changing application code.
"""

from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
import structlog

from btc_collector.models.data_source_config import DataSourceConfig

logger = structlog.get_logger(__name__)


class BlockchainDataProvider(Protocol):
    """Protocol for blockchain data providers."""
    
    def get_block_height(self) -> int:
        """Get current blockchain height."""
        ...
    
    def get_block(self, height_or_hash: str | int) -> Dict[str, Any]:
        """Get block by height or hash."""
        ...
    
    def get_transaction(self, txid: str) -> Dict[str, Any]:
        """Get transaction by ID."""
        ...
    
    def get_address_info(self, address: str) -> Dict[str, Any]:
        """Get address information."""
        ...


class UnifiedDataProvider:
    """
    Unified interface for blockchain data.
    
    Automatically selects the appropriate data source based on configuration.
    Provides consistent data format regardless of source.
    """
    
    def __init__(self, config: Optional[DataSourceConfig] = None):
        self.config = config or DataSourceConfig()
        self.provider = self._create_provider()
        
        source_info = self.config.get_source_info()
        logger.info("Unified data provider initialized", **source_info)
    
    def _create_provider(self):
        """Create the appropriate data provider based on config."""
        source = self.config.data_source
        
        if source == "blockchain_info":
            from btc_collector.core.blockchain_api_client import BlockchainInfoClient
            return BlockchainInfoClient(
                api_key=self.config.blockchain_info_api_key,
                rate_limit_delay=self.config.blockchain_info_rate_limit,
                max_retries=self.config.max_retries,
                timeout=self.config.request_timeout
            )
            
        elif source == "mempool_space":
            from btc_collector.core.blockchain_api_client import MempoolSpaceClient
            return MempoolSpaceClient(
                base_url=self.config.mempool_space_url,
                timeout=self.config.request_timeout
            )
            
        elif source == "blockcypher":
            from btc_collector.core.blockchain_api_client import BlockCypherClient
            return BlockCypherClient(
                api_token=self.config.blockcypher_api_token,
                timeout=self.config.request_timeout
            )
            
        elif source == "rpc":
            from btc_collector.core.rpc_client import BitcoinRPCClient
            from btc_collector.models.config import CollectorConfig
            
            rpc_config = CollectorConfig(
                bitcoin_rpc_host=self.config.bitcoin_rpc_host,
                bitcoin_rpc_port=self.config.bitcoin_rpc_port,
                bitcoin_rpc_user=self.config.bitcoin_rpc_user,
                bitcoin_rpc_password=self.config.bitcoin_rpc_password,
                bitcoin_rpc_timeout=self.config.bitcoin_rpc_timeout,
                db_user=self.config.db_user,
                db_password=self.config.db_password
            )
            return BitcoinRPCClient(rpc_config)
        
        raise ValueError(f"Unknown data source: {source}")
    
    def get_block_height(self) -> int:
        """Get current blockchain height."""
        source = self.config.data_source
        
        if source == "blockchain_info":
            return self.provider.get_block_height()
        elif source == "mempool_space":
            return self.provider.get_block_height()
        elif source == "blockcypher":
            info = self.provider.get_blockchain_info()
            return info.get("height", 0)
        elif source == "rpc":
            return self.provider.get_block_count()
        
        return 0
    
    def get_block(self, height_or_hash) -> Dict[str, Any]:
        """
        Get block by height or hash.
        
        Returns normalized block format regardless of source.
        """
        source = self.config.data_source
        
        if source == "blockchain_info":
            if isinstance(height_or_hash, int):
                raw_block = self.provider.get_block_by_height(height_or_hash)
            else:
                raw_block = self.provider.get_block_by_hash(height_or_hash)
            return self.provider.convert_to_normalized_block(raw_block)
            
        elif source == "mempool_space":
            if isinstance(height_or_hash, int):
                # Get block by height using the new method
                raw_block = self.provider.get_block_by_height(height_or_hash)
            else:
                raw_block = self.provider.get_block(height_or_hash)
            return self.provider.convert_to_normalized_block(raw_block)
            
        elif source == "blockcypher":
            raw_block = self.provider.get_block(str(height_or_hash))
            return self._normalize_blockcypher_block(raw_block)
            
        elif source == "rpc":
            if isinstance(height_or_hash, int):
                block_hash = self.provider.get_block_hash(height_or_hash)
            else:
                block_hash = height_or_hash
            return self.provider.get_block(block_hash, verbosity=2)
        
        raise ValueError(f"Unknown data source: {source}")
    
    def get_latest_blocks(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the latest N blocks."""
        current_height = self.get_block_height()
        blocks = []
        
        for height in range(current_height, max(0, current_height - count), -1):
            try:
                block = self.get_block(height)
                blocks.append(block)
            except Exception as e:
                logger.warning("Failed to get block", height=height, error=str(e))
        
        return blocks
    
    def get_blockchain_stats(self) -> Dict[str, Any]:
        """Get blockchain statistics."""
        source = self.config.data_source
        
        if source == "blockchain_info":
            return self.provider.get_stats()
        elif source == "blockcypher":
            return self.provider.get_blockchain_info()
        else:
            # Build stats from available data
            height = self.get_block_height()
            return {
                "height": height,
                "source": source
            }
    
    def get_address_info(self, address: str) -> Dict[str, Any]:
        """Get address information."""
        source = self.config.data_source
        
        if source == "blockchain_info":
            return self.provider.get_address(address)
        elif source == "blockcypher":
            return self.provider.get_address(address)
        else:
            raise NotImplementedError(f"Address lookup not supported for {source}")
    
    def _normalize_mempool_block(self, raw_block: Dict) -> Dict[str, Any]:
        """Normalize Mempool.space block format."""
        return {
            "hash": raw_block.get("id"),
            "height": raw_block.get("height"),
            "version": raw_block.get("version"),
            "previousblockhash": raw_block.get("previousblockhash"),
            "merkleroot": raw_block.get("merkle_root"),
            "time": raw_block.get("timestamp"),
            "bits": raw_block.get("bits"),
            "nonce": raw_block.get("nonce"),
            "size": raw_block.get("size"),
            "weight": raw_block.get("weight"),
            "nTx": raw_block.get("tx_count"),
            "tx": []  # Need separate call to get transactions
        }
    
    def _normalize_blockcypher_block(self, raw_block: Dict) -> Dict[str, Any]:
        """Normalize BlockCypher block format."""
        return {
            "hash": raw_block.get("hash"),
            "height": raw_block.get("height"),
            "version": raw_block.get("ver"),
            "previousblockhash": raw_block.get("prev_block"),
            "merkleroot": raw_block.get("mrkl_root"),
            "time": raw_block.get("time"),
            "bits": raw_block.get("bits"),
            "nonce": raw_block.get("nonce"),
            "size": raw_block.get("size"),
            "nTx": raw_block.get("n_tx"),
            "tx": raw_block.get("txids", [])
        }


def create_data_provider(config: Optional[DataSourceConfig] = None) -> UnifiedDataProvider:
    """Factory function to create data provider."""
    return UnifiedDataProvider(config)
