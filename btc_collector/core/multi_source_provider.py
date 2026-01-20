"""
Multi-Source Data Provider with Automatic Fallback.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                    BITCOIN DATA SOURCES                      │
├─────────────────────────────────────────────────────────────┤
│  Primary:    mempool.space   (FREE, fastest)                │
│  Fallback 1: blockchain.info (FREE, reliable)               │
│  Fallback 2: blockcypher     (FREE tier, feature-rich)      │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Automatic Failover
                              ↓
                      Unified Output

KHÔNG thể dùng Ethereum RPC thay thế cho Bitcoin!
- Ethereum RPC → Ethereum blockchain (ETH, ERC-20 tokens)
- mempool.space → Bitcoin blockchain (BTC)
- Hoàn toàn khác nhau về protocol, block structure, transaction format
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog

# Import existing clients
from .blockchain_api_client import (
    MempoolSpaceClient,
    BlockchainInfoClient, 
    BlockCypherClient
)

logger = structlog.get_logger(__name__)


class SourceStatus(str, Enum):
    """Data source health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class SourceHealth:
    """Health metrics for a data source."""
    status: SourceStatus = SourceStatus.UNKNOWN
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    avg_response_time_ms: float = 0.0
    total_requests: int = 0
    total_failures: int = 0
    
    def record_success(self, response_time_ms: float):
        """Record successful request."""
        self.last_success = datetime.utcnow()
        self.consecutive_failures = 0
        self.total_requests += 1
        
        # Update rolling average
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = response_time_ms
        else:
            self.avg_response_time_ms = (self.avg_response_time_ms * 0.9) + (response_time_ms * 0.1)
        
        self.status = SourceStatus.HEALTHY
    
    def record_failure(self, error: str = ""):
        """Record failed request."""
        self.last_failure = datetime.utcnow()
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1
        
        if self.consecutive_failures >= 5:
            self.status = SourceStatus.DOWN
        elif self.consecutive_failures >= 2:
            self.status = SourceStatus.DEGRADED
    
    def is_available(self) -> bool:
        """Check if source should be tried."""
        if self.status == SourceStatus.DOWN:
            # Check if enough time has passed to retry (5 minutes)
            if self.last_failure:
                cooldown = timedelta(minutes=5)
                if datetime.utcnow() - self.last_failure < cooldown:
                    return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "consecutive_failures": self.consecutive_failures,
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "success_rate": round((self.total_requests - self.total_failures) / max(1, self.total_requests) * 100, 1)
        }


class MultiSourceProvider:
    """
    Multi-source data provider with automatic fallback.
    
    Priority order:
    1. mempool.space (fastest, best for mempool/fee data)
    2. blockchain.info (reliable, good historical data)
    3. blockcypher (feature-rich, good for tx details)
    
    If primary fails, automatically tries fallback sources.
    """
    
    def __init__(self):
        # Initialize all sources
        self.sources: Dict[str, Any] = {}
        self.health: Dict[str, SourceHealth] = {}
        self.priority: List[str] = []
        
        self._init_sources()
        
        logger.info("MultiSourceProvider initialized",
                   sources=list(self.sources.keys()),
                   priority=self.priority)
    
    def _init_sources(self):
        """Initialize all available data sources."""
        
        # 1. Mempool.space (Primary)
        try:
            mempool_url = os.getenv('MEMPOOL_SPACE_URL', 'https://mempool.space/api')
            self.sources['mempool_space'] = MempoolSpaceClient(mempool_url)
            self.health['mempool_space'] = SourceHealth()
            self.priority.append('mempool_space')
            logger.info("mempool.space initialized", url=mempool_url)
        except Exception as e:
            logger.warning("Failed to init mempool.space", error=str(e))
        
        # 2. Blockchain.info (Fallback 1)
        try:
            api_key = os.getenv('BLOCKCHAIN_INFO_API_KEY', '')
            self.sources['blockchain_info'] = BlockchainInfoClient(api_key if api_key else None)
            self.health['blockchain_info'] = SourceHealth()
            self.priority.append('blockchain_info')
            logger.info("blockchain.info initialized", has_api_key=bool(api_key))
        except Exception as e:
            logger.warning("Failed to init blockchain.info", error=str(e))
        
        # 3. BlockCypher (Fallback 2)
        try:
            token = os.getenv('BLOCKCYPHER_API_TOKEN', '')
            self.sources['blockcypher'] = BlockCypherClient(token if token else None)
            self.health['blockcypher'] = SourceHealth()
            self.priority.append('blockcypher')
            logger.info("blockcypher initialized", has_token=bool(token))
        except Exception as e:
            logger.warning("Failed to init blockcypher", error=str(e))
        
        if not self.sources:
            raise RuntimeError("No data sources available!")
    
    def _try_source(self, source_name: str, method: str, *args, **kwargs) -> Tuple[bool, Any, float]:
        """
        Try calling a method on a source.
        
        Returns:
            Tuple of (success, result, response_time_ms)
        """
        if source_name not in self.sources:
            return False, None, 0
        
        health = self.health[source_name]
        if not health.is_available():
            logger.debug("Source not available", source=source_name)
            return False, None, 0
        
        source = self.sources[source_name]
        
        start = time.time()
        try:
            func = getattr(source, method, None)
            if func is None:
                return False, None, 0
            
            result = func(*args, **kwargs)
            response_time = (time.time() - start) * 1000
            
            health.record_success(response_time)
            logger.debug("Source success", source=source_name, method=method, 
                        response_time_ms=round(response_time, 1))
            
            return True, result, response_time
            
        except Exception as e:
            response_time = (time.time() - start) * 1000
            health.record_failure(str(e))
            logger.warning("Source failed", source=source_name, method=method, 
                          error=str(e), consecutive_failures=health.consecutive_failures)
            return False, None, response_time
    
    def _call_with_fallback(self, method: str, *args, **kwargs) -> Tuple[Any, str]:
        """
        Call method with automatic fallback through sources.
        
        Returns:
            Tuple of (result, source_used)
        """
        errors = []
        
        for source_name in self.priority:
            success, result, _ = self._try_source(source_name, method, *args, **kwargs)
            
            if success and result is not None:
                return result, source_name
            
            errors.append(source_name)
        
        # All sources failed
        logger.error("All sources failed", method=method, tried=errors)
        raise RuntimeError(f"All data sources failed for {method}: {errors}")
    
    # ============================================================
    # Unified API Methods
    # ============================================================
    
    def get_block_height(self) -> Tuple[int, str]:
        """Get current block height with fallback."""
        return self._call_with_fallback('get_block_height')
    
    def get_block(self, height_or_hash) -> Tuple[Dict[str, Any], str]:
        """Get block data with fallback."""
        return self._call_with_fallback('get_block', height_or_hash)
    
    def get_mempool_info(self) -> Tuple[Dict[str, Any], str]:
        """Get mempool info with fallback."""
        # Note: Only mempool.space has good mempool data
        # Others may return limited info
        return self._call_with_fallback('get_mempool_info')
    
    def get_recommended_fees(self) -> Tuple[Dict[str, Any], str]:
        """Get fee recommendations with fallback."""
        return self._call_with_fallback('get_recommended_fees')
    
    def get_transaction(self, txid: str) -> Tuple[Dict[str, Any], str]:
        """Get transaction details with fallback."""
        return self._call_with_fallback('get_transaction', txid)
    
    def get_address_info(self, address: str) -> Tuple[Dict[str, Any], str]:
        """Get address info with fallback."""
        return self._call_with_fallback('get_address', address)
    
    # ============================================================
    # Health & Status
    # ============================================================
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all sources."""
        return {
            source_name: health.to_dict()
            for source_name, health in self.health.items()
        }
    
    def get_available_sources(self) -> List[str]:
        """Get list of currently available sources."""
        return [
            name for name, health in self.health.items()
            if health.is_available()
        ]
    
    def get_primary_source(self) -> Optional[str]:
        """Get current primary (healthiest) source."""
        for source_name in self.priority:
            if self.health[source_name].status == SourceStatus.HEALTHY:
                return source_name
        
        # Return first available
        for source_name in self.priority:
            if self.health[source_name].is_available():
                return source_name
        
        return None
    
    def force_source(self, source_name: str):
        """Force a specific source to be primary (for testing)."""
        if source_name in self.priority:
            self.priority.remove(source_name)
            self.priority.insert(0, source_name)
            logger.info("Forced primary source", source=source_name)


# ============================================================
# Singleton Instance
# ============================================================

_provider: Optional[MultiSourceProvider] = None


def get_multi_source_provider() -> MultiSourceProvider:
    """Get or create multi-source provider singleton."""
    global _provider
    if _provider is None:
        _provider = MultiSourceProvider()
    return _provider


# ============================================================
# Why NOT Ethereum RPC for Bitcoin?
# ============================================================

"""
CRITICAL: Ethereum và Bitcoin là 2 blockchain HOÀN TOÀN KHÁC NHAU!

┌──────────────────────┬────────────────────────┬────────────────────────┐
│                      │ BITCOIN                │ ETHEREUM               │
├──────────────────────┼────────────────────────┼────────────────────────┤
│ Consensus            │ PoW (SHA-256)          │ PoS (Beacon Chain)     │
│ Block Time           │ ~10 minutes            │ ~12 seconds            │
│ Transaction Model    │ UTXO                   │ Account-based          │
│ Smart Contracts      │ Limited (Script)       │ Full (Solidity/EVM)    │
│ Native Currency      │ BTC                    │ ETH                    │
│ RPC Protocol         │ Bitcoin JSON-RPC       │ Ethereum JSON-RPC      │
│ Address Format       │ 1..., 3..., bc1...     │ 0x...                  │
│ Block Structure      │ Merkle Root            │ State Trie             │
└──────────────────────┴────────────────────────┴────────────────────────┘

Ethereum RPC methods (eth_getBlock, eth_getTransaction) trả về data format
hoàn toàn khác với Bitcoin. KHÔNG THỂ dùng thay thế!

FALLBACK SOURCES CHO BITCOIN:
1. mempool.space  - Best for realtime mempool, fees
2. blockchain.info - Good for historical, addresses  
3. blockcypher    - Good for webhooks, tx details
4. blockstream.info - Alternative mempool API
5. Bitcoin Core RPC - If you run your own node (600GB+ storage)
"""
