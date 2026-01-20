"""Bitcoin Core RPC client for blockchain data access."""

import json
import time
from typing import Dict, Any, Optional, List
from decimal import Decimal
import requests
import structlog

from btc_collector.models.config import CollectorConfig
from btc_collector.models.blockchain import RawBlockResponse, RawTransactionResponse

logger = structlog.get_logger(__name__)


class BitcoinRPCError(Exception):
    """Bitcoin RPC specific error."""
    pass


class BitcoinRPCClient:
    """Bitcoin Core JSON-RPC client with retry logic and error handling."""
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'btc-collector/1.0.0'
        })
        
        # RPC endpoint
        self.rpc_url = f"http://{config.bitcoin_rpc_host}:{config.bitcoin_rpc_port}"
        self.auth = (config.bitcoin_rpc_user, config.bitcoin_rpc_password)
        
        logger.info("Bitcoin RPC client initialized", 
                   host=config.bitcoin_rpc_host, 
                   port=config.bitcoin_rpc_port)
    
    def _make_request(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """Make RPC request with retry logic."""
        if params is None:
            params = []
            
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": method,
            "params": params
        }
        
        for attempt in range(self.config.sync_retry_attempts):
            try:
                response = self.session.post(
                    self.rpc_url,
                    json=payload,
                    auth=self.auth,
                    timeout=self.config.bitcoin_rpc_timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                if 'error' in data and data['error'] is not None:
                    error_msg = data['error'].get('message', 'Unknown RPC error')
                    error_code = data['error'].get('code', -1)
                    raise BitcoinRPCError(f"RPC Error {error_code}: {error_msg}")
                
                return data.get('result')
                
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.warning("RPC request failed", 
                             method=method, 
                             attempt=attempt + 1,
                             error=str(e))
                
                if attempt == self.config.sync_retry_attempts - 1:
                    raise BitcoinRPCError(f"RPC request failed after {self.config.sync_retry_attempts} attempts: {e}")
                
                time.sleep(self.config.sync_retry_delay)
        
        raise BitcoinRPCError("Unexpected error in RPC request")
    
    def get_blockchain_info(self) -> Dict[str, Any]:
        """Get blockchain information."""
        return self._make_request("getblockchaininfo")
    
    def get_best_block_hash(self) -> str:
        """Get the hash of the best (tip) block."""
        return self._make_request("getbestblockhash")
    
    def get_block_count(self) -> int:
        """Get the current block height."""
        return self._make_request("getblockcount")
    
    def get_block_hash(self, height: int) -> str:
        """Get block hash by height."""
        return self._make_request("getblockhash", [height])
    
    def get_block(self, block_hash: str, verbosity: int = 2) -> Dict[str, Any]:
        """
        Get block data by hash.
        
        Args:
            block_hash: Block hash
            verbosity: 0=hex, 1=json without tx, 2=json with tx details
        """
        return self._make_request("getblock", [block_hash, verbosity])
    
    def get_raw_transaction(self, tx_hash: str, verbose: bool = True, 
                           block_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Get raw transaction data.
        
        Args:
            tx_hash: Transaction hash
            verbose: Return JSON instead of hex
            block_hash: Block hash (for performance)
        """
        params = [tx_hash, verbose]
        if block_hash:
            params.append(block_hash)
        
        return self._make_request("getrawtransaction", params)
    
    def get_tx_out(self, tx_hash: str, vout: int, 
                   include_mempool: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get UTXO information.
        
        Returns None if UTXO is spent.
        """
        return self._make_request("gettxout", [tx_hash, vout, include_mempool])
    
    def get_block_stats(self, hash_or_height: str | int) -> Dict[str, Any]:
        """Get block statistics."""
        return self._make_request("getblockstats", [hash_or_height])
    
    def validate_address(self, address: str) -> Dict[str, Any]:
        """Validate Bitcoin address."""
        return self._make_request("validateaddress", [address])
    
    def get_mempool_info(self) -> Dict[str, Any]:
        """Get mempool information."""
        return self._make_request("getmempoolinfo")
    
    def get_raw_mempool(self, verbose: bool = False) -> Dict[str, Any] | List[str]:
        """Get raw mempool transactions."""
        return self._make_request("getrawmempool", [verbose])
    
    def test_connection(self) -> bool:
        """Test RPC connection."""
        try:
            info = self.get_blockchain_info()
            logger.info("RPC connection successful", 
                       chain=info.get('chain'),
                       blocks=info.get('blocks'))
            return True
        except Exception as e:
            logger.error("RPC connection failed", error=str(e))
            return False
    
    def get_block_range(self, start_height: int, end_height: int) -> List[Dict[str, Any]]:
        """Get multiple blocks in range (for batch processing)."""
        blocks = []
        
        for height in range(start_height, end_height + 1):
            try:
                block_hash = self.get_block_hash(height)
                block_data = self.get_block(block_hash, verbosity=2)
                blocks.append(block_data)
                
            except BitcoinRPCError as e:
                logger.error("Failed to fetch block", height=height, error=str(e))
                raise
        
        return blocks
    
    def close(self):
        """Close the RPC session."""
        self.session.close()
        logger.info("RPC client session closed")