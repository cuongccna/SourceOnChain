"""
Blockchain.info API Client for Bitcoin blockchain data.

Thay thế Bitcoin Core RPC bằng Blockchain.info Public API.
Không cần chạy node riêng, chỉ cần kết nối internet.

API Documentation: https://www.blockchain.com/explorer/api
"""

import time
import requests
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class BlockchainAPIError(Exception):
    """Blockchain.info API specific error."""
    pass


class BlockchainInfoClient:
    """
    Blockchain.info API client for fetching Bitcoin blockchain data.
    
    Features:
    - No Bitcoin Core node required
    - Free API with rate limiting
    - Supports blocks, transactions, addresses
    
    Rate Limits:
    - 1 request per 10 seconds for /rawblock
    - Higher limits for other endpoints
    """
    
    BASE_URL = "https://blockchain.info"
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 rate_limit_delay: float = 1.0,
                 max_retries: int = 3,
                 timeout: int = 30):
        """
        Initialize Blockchain.info API client.
        
        Args:
            api_key: Optional API key for higher rate limits
            rate_limit_delay: Delay between requests in seconds
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OnChain-Collector/1.0.0',
            'Accept': 'application/json'
        })
        
        self._last_request_time = 0
        
        logger.info("Blockchain.info API client initialized",
                   has_api_key=bool(api_key),
                   rate_limit_delay=rate_limit_delay)
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make API request with retry logic."""
        url = f"{self.BASE_URL}{endpoint}"
        
        if params is None:
            params = {}
        
        # Add API key if available
        if self.api_key:
            params['api_code'] = self.api_key
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = int(response.headers.get('Retry-After', 30))
                    logger.warning("Rate limited, waiting", wait_time=wait_time)
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                return response.json()
                
            except requests.exceptions.JSONDecodeError:
                # Some endpoints return plain text
                return {"raw": response.text}
                
            except requests.RequestException as e:
                logger.warning("API request failed",
                             endpoint=endpoint,
                             attempt=attempt + 1,
                             error=str(e))
                
                if attempt == self.max_retries - 1:
                    raise BlockchainAPIError(f"Request failed after {self.max_retries} attempts: {e}")
                
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise BlockchainAPIError("Unexpected error in API request")
    
    # ==================== Block Methods ====================
    
    def get_latest_block(self) -> Dict[str, Any]:
        """
        Get latest block information.
        
        Returns:
            {
                "hash": "...",
                "time": 1234567890,
                "block_index": 123456,
                "height": 879500,
                "txIndexes": [...]
            }
        """
        return self._make_request("/latestblock")
    
    def get_block_height(self) -> int:
        """Get current blockchain height."""
        latest = self.get_latest_block()
        return latest.get("height", 0)
    
    def get_block_by_hash(self, block_hash: str) -> Dict[str, Any]:
        """
        Get full block data by hash.
        
        Returns block with all transactions.
        """
        return self._make_request(f"/rawblock/{block_hash}")
    
    def get_block_by_height(self, height: int) -> Dict[str, Any]:
        """
        Get block data by height.
        
        Note: This requires getting hash first, then block data.
        """
        # Try getting block directly via rawblock endpoint with height
        try:
            # First try: get latest block and work backwards if needed
            latest = self.get_latest_block()
            latest_height = latest.get("height", 0)
            
            if height == latest_height:
                # Get the latest block by hash
                return self.get_block_by_hash(latest.get("hash"))
            
            # For other heights, try block-height endpoint
            response = self._make_request(f"/block-height/{height}", {"format": "json"})
            
            if isinstance(response, dict) and "blocks" in response and len(response["blocks"]) > 0:
                return response["blocks"][0]
            
            # If block-height fails, return a minimal block structure
            # This happens when API has rate limits or issues
            return {
                "height": height,
                "hash": f"unknown_at_{height}",
                "time": 0,
                "n_tx": 0,
                "tx": [],
                "size": 0,
                "error": "Could not fetch full block data"
            }
            
        except Exception as e:
            # Return minimal structure instead of raising
            return {
                "height": height,
                "hash": f"error_at_{height}",
                "time": 0,
                "n_tx": 0,
                "tx": [],
                "size": 0,
                "error": str(e)
            }
    
    def get_blocks_for_day(self, timestamp_ms: int) -> List[Dict[str, Any]]:
        """
        Get all blocks for a specific day.
        
        Args:
            timestamp_ms: Unix timestamp in milliseconds
        """
        return self._make_request(f"/blocks/{timestamp_ms}", {"format": "json"})
    
    # ==================== Transaction Methods ====================
    
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get transaction by hash.
        
        Returns:
            {
                "hash": "...",
                "ver": 2,
                "vin_sz": 1,
                "vout_sz": 2,
                "size": 225,
                "weight": 900,
                "fee": 10000,
                "inputs": [...],
                "out": [...]
            }
        """
        return self._make_request(f"/rawtx/{tx_hash}")
    
    def get_unconfirmed_transactions(self) -> List[Dict[str, Any]]:
        """Get latest unconfirmed transactions (mempool)."""
        return self._make_request("/unconfirmed-transactions", {"format": "json"})
    
    # ==================== Address Methods ====================
    
    def get_address(self, address: str, 
                    limit: int = 50, 
                    offset: int = 0) -> Dict[str, Any]:
        """
        Get address information with transactions.
        
        Args:
            address: Bitcoin address
            limit: Max transactions to return
            offset: Pagination offset
            
        Returns:
            {
                "hash160": "...",
                "address": "...",
                "n_tx": 100,
                "total_received": 1000000000,
                "total_sent": 500000000,
                "final_balance": 500000000,
                "txs": [...]
            }
        """
        return self._make_request(f"/rawaddr/{address}", {
            "limit": limit,
            "offset": offset
        })
    
    def get_address_balance(self, address: str) -> Dict[str, int]:
        """
        Get address balance only (faster than full address data).
        
        Returns:
            {
                "final_balance": 500000000,
                "n_tx": 100,
                "total_received": 1000000000
            }
        """
        return self._make_request(f"/balance", {"active": address})
    
    def get_multi_address(self, addresses: List[str]) -> Dict[str, Any]:
        """
        Get data for multiple addresses at once.
        
        Args:
            addresses: List of Bitcoin addresses (max 100)
        """
        if len(addresses) > 100:
            raise BlockchainAPIError("Maximum 100 addresses per request")
        
        return self._make_request("/multiaddr", {
            "active": "|".join(addresses)
        })
    
    def get_address_unspent(self, address: str) -> List[Dict[str, Any]]:
        """
        Get unspent outputs (UTXOs) for an address.
        
        Returns list of UTXOs:
            [
                {
                    "tx_hash": "...",
                    "tx_output_n": 0,
                    "value": 100000000,
                    "confirmations": 6
                }
            ]
        """
        return self._make_request(f"/unspent", {"active": address})
    
    # ==================== Charts & Stats Methods ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get blockchain statistics.
        
        Returns:
            {
                "market_price_usd": 50000.0,
                "hash_rate": 200000000,
                "total_fees_btc": 100,
                "n_btc_mined": 900000000000,
                "n_tx": 500000,
                "n_blocks_mined": 144,
                "totalbc": 1900000000000000,
                "estimated_transaction_volume_usd": 1000000000,
                ...
            }
        """
        return self._make_request("/stats")
    
    def get_chart_data(self, chart_name: str, 
                       timespan: str = "1year",
                       rolling_average: Optional[str] = None) -> Dict[str, Any]:
        """
        Get historical chart data.
        
        Chart names:
        - total-bitcoins
        - market-price
        - hash-rate
        - difficulty
        - miners-revenue
        - transaction-fees
        - n-transactions
        - n-unique-addresses
        - avg-block-size
        
        Args:
            chart_name: Name of the chart
            timespan: Time period (e.g., "1year", "30days", "all")
            rolling_average: Rolling average period (e.g., "8hours", "1day")
        """
        params = {"timespan": timespan, "format": "json"}
        if rolling_average:
            params["rollingAverage"] = rolling_average
            
        return self._make_request(f"/charts/{chart_name}", params)
    
    # ==================== Conversion Methods ====================
    
    def convert_to_normalized_block(self, raw_block: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Blockchain.info block format to normalized format.
        
        Makes it compatible with existing btc_collector processing.
        """
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
            "weight": raw_block.get("weight", raw_block.get("size", 0) * 4),
            "tx": [self.convert_to_normalized_tx(tx) for tx in raw_block.get("tx", [])],
            "nTx": raw_block.get("n_tx", len(raw_block.get("tx", [])))
        }
    
    def convert_to_normalized_tx(self, raw_tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Blockchain.info transaction format to normalized format.
        """
        # Convert inputs
        vin = []
        for inp in raw_tx.get("inputs", []):
            prev_out = inp.get("prev_out", {})
            vin.append({
                "txid": prev_out.get("tx_index"),
                "vout": prev_out.get("n"),
                "scriptSig": {"hex": inp.get("script", "")},
                "sequence": inp.get("sequence", 0xffffffff),
                "value": prev_out.get("value", 0) / 100000000  # satoshi to BTC
            })
        
        # Convert outputs
        vout = []
        for out in raw_tx.get("out", []):
            vout.append({
                "value": out.get("value", 0) / 100000000,  # satoshi to BTC
                "n": out.get("n"),
                "scriptPubKey": {
                    "hex": out.get("script", ""),
                    "addresses": [out.get("addr")] if out.get("addr") else []
                }
            })
        
        return {
            "txid": raw_tx.get("hash"),
            "hash": raw_tx.get("hash"),
            "version": raw_tx.get("ver"),
            "size": raw_tx.get("size"),
            "vsize": raw_tx.get("size"),  # Approximation
            "weight": raw_tx.get("weight", raw_tx.get("size", 0) * 4),
            "locktime": raw_tx.get("lock_time", 0),
            "vin": vin,
            "vout": vout,
            "fee": raw_tx.get("fee", 0) / 100000000 if raw_tx.get("fee") else 0
        }


# ==================== Alternative APIs ====================

class MempoolSpaceClient:
    """
    Mempool.space API client - FREE, no API key required.
    
    Features:
    - Real-time mempool data
    - Accurate fee estimates
    - Block and transaction data
    - Address information
    - Lightning network data
    
    Rate Limits: ~10 requests/second (generous)
    API Docs: https://mempool.space/docs/api
    """
    
    BASE_URL = "https://mempool.space/api"
    
    def __init__(self, base_url: str = None, timeout: int = 30, rate_limit_delay: float = 0.1):
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OnChain-Collector/1.0.0'
        })
        self._last_request_time = 0
        
        logger.info("Mempool.space API client initialized",
                   base_url=self.base_url,
                   rate_limit_delay=rate_limit_delay)
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    def _get(self, endpoint: str) -> Any:
        """Make GET request with rate limiting."""
        self._rate_limit()
        response = self.session.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
        response.raise_for_status()
        
        # Handle plain text responses
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            return response.json()
        return response.text
    
    # ==================== Block Methods ====================
    
    def get_block_height(self) -> int:
        """Get current block height."""
        return int(self._get("/blocks/tip/height"))
    
    def get_block_hash(self, height: int) -> str:
        """Get block hash at specific height."""
        return self._get(f"/block-height/{height}")
    
    def get_block(self, block_hash: str) -> Dict[str, Any]:
        """Get block by hash."""
        return self._get(f"/block/{block_hash}")
    
    def get_block_by_height(self, height: int) -> Dict[str, Any]:
        """Get block by height (convenience method)."""
        block_hash = self.get_block_hash(height)
        return self.get_block(block_hash)
    
    def get_block_txids(self, block_hash: str) -> List[str]:
        """Get all transaction IDs in a block."""
        return self._get(f"/block/{block_hash}/txids")
    
    def get_block_txs(self, block_hash: str, start_index: int = 0) -> List[Dict[str, Any]]:
        """Get block transactions (25 at a time)."""
        return self._get(f"/block/{block_hash}/txs/{start_index}")
    
    def get_blocks(self, start_height: int = None) -> List[Dict[str, Any]]:
        """Get latest 10 blocks (or from specific height)."""
        if start_height:
            return self._get(f"/blocks/{start_height}")
        return self._get("/blocks")
    
    # ==================== Transaction Methods ====================
    
    def get_transaction(self, txid: str) -> Dict[str, Any]:
        """Get transaction by ID."""
        return self._get(f"/tx/{txid}")
    
    def get_transaction_hex(self, txid: str) -> str:
        """Get raw transaction hex."""
        return self._get(f"/tx/{txid}/hex")
    
    def get_transaction_status(self, txid: str) -> Dict[str, Any]:
        """Get transaction confirmation status."""
        return self._get(f"/tx/{txid}/status")
    
    # ==================== Address Methods ====================
    
    def get_address(self, address: str) -> Dict[str, Any]:
        """
        Get address information.
        
        Returns:
            {
                "address": "...",
                "chain_stats": {
                    "funded_txo_count": 10,
                    "funded_txo_sum": 1000000000,
                    "spent_txo_count": 5,
                    "spent_txo_sum": 500000000,
                    "tx_count": 15
                },
                "mempool_stats": {...}
            }
        """
        return self._get(f"/address/{address}")
    
    def get_address_txs(self, address: str) -> List[Dict[str, Any]]:
        """Get address transactions (up to 50)."""
        return self._get(f"/address/{address}/txs")
    
    def get_address_utxos(self, address: str) -> List[Dict[str, Any]]:
        """
        Get address UTXOs.
        
        Returns:
            [
                {
                    "txid": "...",
                    "vout": 0,
                    "status": {...},
                    "value": 100000000
                }
            ]
        """
        return self._get(f"/address/{address}/utxo")
    
    # ==================== Mempool Methods ====================
    
    def get_mempool_info(self) -> Dict[str, Any]:
        """
        Get mempool statistics.
        
        Returns:
            {
                "count": 5000,
                "vsize": 3000000,
                "total_fee": 10000000,
                "fee_histogram": [...]
            }
        """
        return self._get("/mempool")
    
    def get_mempool_txids(self) -> List[str]:
        """Get all transaction IDs in mempool."""
        return self._get("/mempool/txids")
    
    def get_mempool_recent(self) -> List[Dict[str, Any]]:
        """Get 10 most recent mempool transactions."""
        return self._get("/mempool/recent")
    
    # ==================== Fee Estimation ====================
    
    def get_recommended_fees(self) -> Dict[str, int]:
        """
        Get recommended transaction fees.
        
        Returns:
            {
                "fastestFee": 20,      # Next block
                "halfHourFee": 15,     # ~3 blocks
                "hourFee": 10,         # ~6 blocks
                "economyFee": 5,       # ~12 blocks
                "minimumFee": 1        # Minimum relay fee
            }
        """
        return self._get("/v1/fees/recommended")
    
    def get_fee_histogram(self) -> List[List]:
        """Get mempool fee histogram."""
        return self._get("/v1/fees/mempool-blocks")
    
    # ==================== Mining/Difficulty ====================
    
    def get_difficulty_adjustment(self) -> Dict[str, Any]:
        """
        Get difficulty adjustment info.
        
        Returns:
            {
                "progressPercent": 50.5,
                "difficultyChange": 5.2,
                "estimatedRetargetDate": 1234567890,
                "remainingBlocks": 1000,
                "remainingTime": 600000,
                "previousRetarget": -2.1,
                "nextRetargetHeight": 850000
            }
        """
        return self._get("/v1/difficulty-adjustment")
    
    def get_hashrate(self, timescale: str = "3m") -> Dict[str, Any]:
        """Get network hashrate (1m, 3m, 6m, 1y, 2y, 3y)."""
        return self._get(f"/v1/mining/hashrate/{timescale}")
    
    # ==================== Normalization ====================
    
    def convert_to_normalized_block(self, raw_block: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Mempool.space block format to normalized format."""
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
            "tx": []  # Transactions fetched separately
        }
    
    def convert_to_normalized_tx(self, raw_tx: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Mempool.space transaction format to normalized format."""
        # Convert inputs
        vin = []
        for inp in raw_tx.get("vin", []):
            vin.append({
                "txid": inp.get("txid"),
                "vout": inp.get("vout"),
                "scriptSig": {"hex": inp.get("scriptsig", "")},
                "sequence": inp.get("sequence", 0xffffffff),
                "witness": inp.get("witness", []),
                "prevout": inp.get("prevout", {})
            })
        
        # Convert outputs
        vout = []
        for idx, out in enumerate(raw_tx.get("vout", [])):
            vout.append({
                "value": out.get("value", 0) / 100000000,
                "n": idx,
                "scriptPubKey": {
                    "hex": out.get("scriptpubkey", ""),
                    "type": out.get("scriptpubkey_type", ""),
                    "address": out.get("scriptpubkey_address")
                }
            })
        
        return {
            "txid": raw_tx.get("txid"),
            "hash": raw_tx.get("txid"),
            "version": raw_tx.get("version"),
            "size": raw_tx.get("size"),
            "vsize": raw_tx.get("weight", 0) // 4 if raw_tx.get("weight") else raw_tx.get("size"),
            "weight": raw_tx.get("weight"),
            "locktime": raw_tx.get("locktime", 0),
            "vin": vin,
            "vout": vout,
            "fee": raw_tx.get("fee", 0) / 100000000 if raw_tx.get("fee") else 0,
            "status": raw_tx.get("status", {})
        }


class BlockCypherClient:
    """
    BlockCypher API client (alternative with more features).
    
    API Docs: https://www.blockcypher.com/dev/bitcoin/
    Free tier: 3 requests/second, 200 requests/hour
    """
    
    BASE_URL = "https://api.blockcypher.com/v1/btc/main"
    
    def __init__(self, api_token: Optional[str] = None, timeout: int = 30):
        self.api_token = api_token
        self.timeout = timeout
        self.session = requests.Session()
    
    def _get_params(self) -> Dict:
        """Get default params with token if available."""
        return {"token": self.api_token} if self.api_token else {}
    
    def get_blockchain_info(self) -> Dict[str, Any]:
        """Get blockchain information."""
        response = self.session.get(self.BASE_URL, params=self._get_params(), timeout=self.timeout)
        return response.json()
    
    def get_block(self, block_hash_or_height: str) -> Dict[str, Any]:
        """Get block by hash or height."""
        response = self.session.get(
            f"{self.BASE_URL}/blocks/{block_hash_or_height}",
            params=self._get_params(),
            timeout=self.timeout
        )
        return response.json()
    
    def get_address(self, address: str) -> Dict[str, Any]:
        """Get address information."""
        response = self.session.get(
            f"{self.BASE_URL}/addrs/{address}",
            params=self._get_params(),
            timeout=self.timeout
        )
        return response.json()
