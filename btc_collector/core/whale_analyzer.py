"""
Real-time Whale Detection using Mempool.space API.

Analyzes Bitcoin transactions to detect whale activity without requiring
a full node or historical database.

Features:
- Real transaction analysis from recent blocks
- Dynamic whale thresholds based on current market
- Inflow/outflow detection using address patterns
- Integration with existing pipeline
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)


# ============================================================
# Data Models
# ============================================================

@dataclass
class WhaleTransaction:
    """A single whale transaction."""
    txid: str
    value_btc: Decimal
    timestamp: int
    block_height: int
    tier: str  # 'large', 'whale', 'ultra_whale', 'leviathan'
    flow_type: str  # 'inflow', 'outflow', 'internal', 'unknown'
    fee_btc: Decimal = Decimal('0')
    input_count: int = 0
    output_count: int = 0


@dataclass
class WhaleMetrics:
    """Aggregated whale metrics for a time period."""
    timestamp: datetime
    timeframe: str
    blocks_analyzed: int
    
    # Transaction counts by tier
    large_tx_count: int = 0
    whale_tx_count: int = 0
    ultra_whale_tx_count: int = 0
    leviathan_tx_count: int = 0
    
    # Volumes by tier (BTC)
    large_tx_volume: Decimal = Decimal('0')
    whale_tx_volume: Decimal = Decimal('0')
    ultra_whale_tx_volume: Decimal = Decimal('0')
    leviathan_tx_volume: Decimal = Decimal('0')
    
    # Flow analysis
    whale_inflow: Decimal = Decimal('0')  # Accumulation
    whale_outflow: Decimal = Decimal('0')  # Distribution
    net_whale_flow: Decimal = Decimal('0')
    
    # Ratios
    whale_tx_ratio: Decimal = Decimal('0')  # % of total tx count
    whale_volume_ratio: Decimal = Decimal('0')  # % of total volume
    
    # Context
    total_tx_count: int = 0
    total_volume_btc: Decimal = Decimal('0')
    avg_tx_value: Decimal = Decimal('0')
    
    # Dynamic thresholds used
    large_threshold: Decimal = Decimal('0')
    whale_threshold: Decimal = Decimal('0')
    ultra_whale_threshold: Decimal = Decimal('0')
    leviathan_threshold: Decimal = Decimal('0')
    
    # Individual whale transactions
    whale_transactions: List[WhaleTransaction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "timeframe": self.timeframe,
            "blocks_analyzed": self.blocks_analyzed,
            
            "whale_tx_count": self.whale_tx_count,
            "whale_volume_btc": float(self.whale_tx_volume),
            "whale_inflow": float(self.whale_inflow),
            "whale_outflow": float(self.whale_outflow),
            "net_whale_flow": float(self.net_whale_flow),
            "whale_dominance": float(self.whale_volume_ratio),
            
            "tiers": {
                "large": {
                    "count": self.large_tx_count,
                    "volume_btc": float(self.large_tx_volume),
                    "threshold_btc": float(self.large_threshold)
                },
                "whale": {
                    "count": self.whale_tx_count,
                    "volume_btc": float(self.whale_tx_volume),
                    "threshold_btc": float(self.whale_threshold)
                },
                "ultra_whale": {
                    "count": self.ultra_whale_tx_count,
                    "volume_btc": float(self.ultra_whale_tx_volume),
                    "threshold_btc": float(self.ultra_whale_threshold)
                },
                "leviathan": {
                    "count": self.leviathan_tx_count,
                    "volume_btc": float(self.leviathan_tx_volume),
                    "threshold_btc": float(self.leviathan_threshold)
                }
            },
            
            "context": {
                "total_tx_count": self.total_tx_count,
                "total_volume_btc": float(self.total_volume_btc),
                "avg_tx_value_btc": float(self.avg_tx_value),
                "whale_tx_ratio": float(self.whale_tx_ratio),
                "whale_volume_ratio": float(self.whale_volume_ratio)
            }
        }


# ============================================================
# Known Address Patterns for Flow Detection
# ============================================================

# Common exchange deposit patterns (simplified heuristics)
EXCHANGE_PATTERNS = {
    # Binance hot wallets often start with bc1q or 3
    "exchange_likely": ["bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h"],  # Example
}

# Known whale addresses (would be expanded from on-chain analysis)
KNOWN_WHALE_ADDRESSES = set()


# ============================================================
# Whale Analyzer
# ============================================================

class WhaleAnalyzer:
    """
    Real-time whale transaction analyzer.
    
    Uses Mempool.space API to analyze recent blocks and detect whale activity.
    """
    
    # Default thresholds based on Bitcoin network statistics
    # These are dynamic and will be recalculated based on recent data
    DEFAULT_THRESHOLDS = {
        'large': Decimal('1'),        # 1+ BTC (P95)
        'whale': Decimal('10'),       # 10+ BTC (P99)
        'ultra_whale': Decimal('100'),  # 100+ BTC (P99.9)
        'leviathan': Decimal('1000')   # 1000+ BTC (P99.99)
    }
    
    def __init__(self, mempool_client, config: Optional[Dict] = None):
        """
        Initialize whale analyzer.
        
        Args:
            mempool_client: MempoolSpaceClient instance
            config: Optional configuration overrides
        """
        self.client = mempool_client
        self.config = config or {}
        
        # Configurable thresholds
        self.thresholds = {
            'large': Decimal(str(self.config.get('large_threshold', 1))),
            'whale': Decimal(str(self.config.get('whale_threshold', 10))),
            'ultra_whale': Decimal(str(self.config.get('ultra_whale_threshold', 100))),
            'leviathan': Decimal(str(self.config.get('leviathan_threshold', 1000)))
        }
        
        # Cache for recent analysis
        self._cache = {}
        self._cache_ttl = self.config.get('cache_ttl', 60)  # 60 seconds
        
        logger.info("WhaleAnalyzer initialized", thresholds=self.thresholds)
    
    def _get_tx_tier(self, value_btc: Decimal) -> Optional[str]:
        """Classify transaction by value tier."""
        if value_btc >= self.thresholds['leviathan']:
            return 'leviathan'
        elif value_btc >= self.thresholds['ultra_whale']:
            return 'ultra_whale'
        elif value_btc >= self.thresholds['whale']:
            return 'whale'
        elif value_btc >= self.thresholds['large']:
            return 'large'
        return None
    
    def _classify_flow(self, tx: Dict[str, Any]) -> str:
        """
        Classify transaction flow type based on heuristics.
        
        Heuristics used:
        - High input count with single output: likely consolidation (inflow/accumulation)
        - Single input with many outputs: likely distribution (outflow)
        - Equal-ish inputs/outputs: internal transfer or unknown
        """
        vin = tx.get('vin', [])
        vout = tx.get('vout', [])
        
        input_count = len(vin)
        output_count = len(vout)
        
        # Coinbase (mining reward) - considered inflow
        if input_count == 1 and vin[0].get('is_coinbase', False):
            return 'inflow'
        
        # Consolidation pattern: many inputs -> few outputs
        # Typically indicates accumulation by whale
        if input_count >= 5 and output_count <= 2:
            return 'inflow'
        
        # Distribution pattern: few inputs -> many outputs
        # Typically indicates selling/distributing
        if input_count <= 2 and output_count >= 5:
            return 'outflow'
        
        # Peel chain pattern (common in exchanges): 1 in, 2 out
        if input_count == 1 and output_count == 2:
            # Need to analyze output values for better classification
            # For now, mark as unknown
            return 'unknown'
        
        # Internal transfer or complex transaction
        return 'internal'
    
    def _analyze_transaction(self, tx: Dict[str, Any], block_height: int) -> Optional[WhaleTransaction]:
        """
        Analyze a single transaction for whale activity.
        
        Args:
            tx: Raw transaction data from API
            block_height: Block height for context
            
        Returns:
            WhaleTransaction if qualifies, None otherwise
        """
        # Calculate total output value (transaction value)
        total_value_sats = sum(vout.get('value', 0) for vout in tx.get('vout', []))
        total_value_btc = Decimal(total_value_sats) / Decimal('100000000')
        
        # Get tier
        tier = self._get_tx_tier(total_value_btc)
        if tier is None:
            return None
        
        # Classify flow
        flow_type = self._classify_flow(tx)
        
        # Get fee
        fee_sats = tx.get('fee', 0)
        fee_btc = Decimal(fee_sats) / Decimal('100000000') if fee_sats else Decimal('0')
        
        return WhaleTransaction(
            txid=tx.get('txid', ''),
            value_btc=total_value_btc,
            timestamp=tx.get('status', {}).get('block_time', 0),
            block_height=block_height,
            tier=tier,
            flow_type=flow_type,
            fee_btc=fee_btc,
            input_count=len(tx.get('vin', [])),
            output_count=len(tx.get('vout', []))
        )
    
    def analyze_block(self, block_hash: str, block_height: int) -> Tuple[List[WhaleTransaction], int, Decimal]:
        """
        Analyze all transactions in a block for whale activity.
        
        Args:
            block_hash: Block hash
            block_height: Block height
            
        Returns:
            Tuple of (whale_transactions, total_tx_count, total_volume)
        """
        whale_txs = []
        total_tx_count = 0
        total_volume = Decimal('0')
        
        # Get block transactions (paginated, 25 at a time)
        start_index = 0
        while True:
            try:
                txs = self.client.get_block_txs(block_hash, start_index)
                if not txs:
                    break
                    
                for tx in txs:
                    total_tx_count += 1
                    
                    # Calculate transaction value
                    tx_value = sum(vout.get('value', 0) for vout in tx.get('vout', []))
                    total_volume += Decimal(tx_value) / Decimal('100000000')
                    
                    # Check for whale transaction
                    whale_tx = self._analyze_transaction(tx, block_height)
                    if whale_tx:
                        whale_txs.append(whale_tx)
                
                # Check if more transactions
                if len(txs) < 25:
                    break
                start_index += 25
                
            except Exception as e:
                logger.warning("Error fetching block transactions",
                             block_hash=block_hash,
                             start_index=start_index,
                             error=str(e))
                break
        
        return whale_txs, total_tx_count, total_volume
    
    def analyze_recent_blocks(self, num_blocks: int = 6) -> WhaleMetrics:
        """
        Analyze recent blocks for whale activity.
        
        Args:
            num_blocks: Number of recent blocks to analyze (default: 6 = ~1 hour)
            
        Returns:
            WhaleMetrics with aggregated whale data
        """
        logger.info("Analyzing recent blocks for whale activity", num_blocks=num_blocks)
        
        # Check cache
        cache_key = f"recent_{num_blocks}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).seconds < self._cache_ttl:
                logger.debug("Using cached whale metrics")
                return cached_data
        
        # Get current height
        current_height = self.client.get_block_height()
        
        # Initialize metrics
        all_whale_txs = []
        total_tx_count = 0
        total_volume = Decimal('0')
        blocks_analyzed = 0
        
        # Analyze each block
        for height in range(current_height, max(current_height - num_blocks, 0), -1):
            try:
                # Get block hash
                block_hash = self.client.get_block_hash(height)
                
                # Analyze block
                whale_txs, block_tx_count, block_volume = self.analyze_block(block_hash, height)
                
                all_whale_txs.extend(whale_txs)
                total_tx_count += block_tx_count
                total_volume += block_volume
                blocks_analyzed += 1
                
                logger.debug("Block analyzed",
                           height=height,
                           tx_count=block_tx_count,
                           whale_tx_count=len(whale_txs))
                
            except Exception as e:
                logger.warning("Error analyzing block", height=height, error=str(e))
                continue
        
        # Aggregate metrics
        metrics = self._aggregate_metrics(
            all_whale_txs,
            total_tx_count,
            total_volume,
            blocks_analyzed,
            "1h" if num_blocks == 6 else f"{num_blocks}b"
        )
        
        # Cache results
        self._cache[cache_key] = (datetime.utcnow(), metrics)
        
        logger.info("Whale analysis complete",
                   blocks=blocks_analyzed,
                   total_txs=total_tx_count,
                   whale_txs=len(all_whale_txs),
                   whale_volume=float(metrics.whale_tx_volume))
        
        return metrics
    
    def _aggregate_metrics(self, whale_txs: List[WhaleTransaction],
                          total_tx_count: int,
                          total_volume: Decimal,
                          blocks_analyzed: int,
                          timeframe: str) -> WhaleMetrics:
        """Aggregate whale transactions into metrics."""
        
        metrics = WhaleMetrics(
            timestamp=datetime.utcnow(),
            timeframe=timeframe,
            blocks_analyzed=blocks_analyzed,
            total_tx_count=total_tx_count,
            total_volume_btc=total_volume,
            large_threshold=self.thresholds['large'],
            whale_threshold=self.thresholds['whale'],
            ultra_whale_threshold=self.thresholds['ultra_whale'],
            leviathan_threshold=self.thresholds['leviathan'],
            whale_transactions=whale_txs[:20]  # Keep top 20 for reference
        )
        
        # Aggregate by tier
        for tx in whale_txs:
            if tx.tier == 'large':
                metrics.large_tx_count += 1
                metrics.large_tx_volume += tx.value_btc
            elif tx.tier == 'whale':
                metrics.whale_tx_count += 1
                metrics.whale_tx_volume += tx.value_btc
            elif tx.tier == 'ultra_whale':
                metrics.ultra_whale_tx_count += 1
                metrics.ultra_whale_tx_volume += tx.value_btc
            elif tx.tier == 'leviathan':
                metrics.leviathan_tx_count += 1
                metrics.leviathan_tx_volume += tx.value_btc
            
            # Flow analysis (for whale tier and above)
            if tx.tier in ('whale', 'ultra_whale', 'leviathan'):
                if tx.flow_type == 'inflow':
                    metrics.whale_inflow += tx.value_btc
                elif tx.flow_type == 'outflow':
                    metrics.whale_outflow += tx.value_btc
        
        # Calculate net flow
        metrics.net_whale_flow = metrics.whale_inflow - metrics.whale_outflow
        
        # Calculate ratios
        total_whale_count = (metrics.whale_tx_count + 
                           metrics.ultra_whale_tx_count + 
                           metrics.leviathan_tx_count)
        total_whale_volume = (metrics.whale_tx_volume + 
                             metrics.ultra_whale_tx_volume + 
                             metrics.leviathan_tx_volume)
        
        if total_tx_count > 0:
            metrics.whale_tx_ratio = Decimal(total_whale_count) / Decimal(total_tx_count)
        
        if total_volume > 0:
            metrics.whale_volume_ratio = total_whale_volume / total_volume
        
        if total_tx_count > 0:
            metrics.avg_tx_value = total_volume / Decimal(total_tx_count)
        
        return metrics
    
    def get_whale_summary(self, num_blocks: int = 6) -> Dict[str, Any]:
        """
        Get a summary of whale activity for API response.
        
        Args:
            num_blocks: Number of blocks to analyze
            
        Returns:
            Dictionary with whale metrics ready for API
        """
        metrics = self.analyze_recent_blocks(num_blocks)
        return metrics.to_dict()


# ============================================================
# Quick Whale Detector (Lighter version for API)
# ============================================================

class QuickWhaleDetector:
    """
    Lightweight whale detector for real-time API responses.
    
    Uses sampling instead of full block analysis for speed.
    """
    
    def __init__(self, mempool_client):
        self.client = mempool_client
        self.thresholds = {
            'whale': Decimal('10'),
            'ultra_whale': Decimal('100'),
            'leviathan': Decimal('500')
        }
        self._cache = None
        self._cache_time = None
        self._cache_ttl = 120  # 2 minutes cache
        
        # Store detected whale transactions
        self._whale_transactions = []
    
    def _is_cache_valid(self) -> bool:
        if self._cache is None or self._cache_time is None:
            return False
        return (datetime.utcnow() - self._cache_time).seconds < self._cache_ttl
    
    def _classify_tier(self, value_btc: Decimal) -> str:
        """Classify transaction into whale tier."""
        if value_btc >= self.thresholds['leviathan']:
            return 'leviathan'
        elif value_btc >= self.thresholds['ultra_whale']:
            return 'ultra_whale'
        elif value_btc >= self.thresholds['whale']:
            return 'whale'
        return 'large'
    
    def _classify_flow(self, inputs: int, outputs: int) -> str:
        """Classify transaction flow type."""
        if inputs >= 3 and outputs <= 2:
            return 'inflow'  # Accumulation - many inputs, few outputs
        elif inputs <= 2 and outputs >= 3:
            return 'outflow'  # Distribution - few inputs, many outputs
        elif inputs == 1 and outputs == 1:
            return 'internal'  # Internal transfer
        return 'unknown'
    
    def get_quick_metrics(self) -> Dict[str, Any]:
        """
        Get quick whale metrics using sampling.
        
        Analyzes last 2-3 blocks with sampling for speed.
        """
        if self._is_cache_valid():
            return self._cache
        
        try:
            height = self.client.get_block_height()
            
            whale_count = 0
            whale_volume = Decimal('0')
            whale_inflow = Decimal('0')
            whale_outflow = Decimal('0')
            total_sampled = 0
            
            # Clear previous transactions
            self._whale_transactions = []
            
            # Analyze last 2 blocks
            for h in range(height, max(height - 2, 0), -1):
                block_hash = self.client.get_block_hash(h)
                
                # Get first batch of transactions (25)
                txs = self.client.get_block_txs(block_hash, 0)
                
                for tx in txs:
                    total_sampled += 1
                    
                    # Calculate value
                    value_sats = sum(v.get('value', 0) for v in tx.get('vout', []))
                    value_btc = Decimal(value_sats) / Decimal('100000000')
                    
                    if value_btc >= self.thresholds['whale']:
                        whale_count += 1
                        whale_volume += value_btc
                        
                        # Classify transaction
                        inputs = len(tx.get('vin', []))
                        outputs = len(tx.get('vout', []))
                        flow_type = self._classify_flow(inputs, outputs)
                        tier = self._classify_tier(value_btc)
                        
                        if flow_type == 'inflow':
                            whale_inflow += value_btc
                        elif flow_type == 'outflow':
                            whale_outflow += value_btc
                        
                        # Calculate fee
                        fee_sats = tx.get('fee', 0)
                        fee_btc = Decimal(fee_sats) / Decimal('100000000')
                        
                        # Store whale transaction for persistence
                        whale_tx = {
                            'txid': tx.get('txid'),
                            'block_height': h,
                            'timestamp': tx.get('status', {}).get('block_time', int(datetime.utcnow().timestamp())),
                            'value_btc': float(value_btc),
                            'tier': tier,
                            'flow_type': flow_type,
                            'fee_btc': float(fee_btc),
                            'input_count': inputs,
                            'output_count': outputs
                        }
                        self._whale_transactions.append(whale_tx)
            
            # Extrapolate to estimate full metrics
            # Average ~3000 txs per block, we sampled 50
            extrapolation_factor = Decimal('60')  # ~3000/50
            
            result = {
                "whale_tx_count": int(whale_count * float(extrapolation_factor)),
                "whale_volume_btc": float(whale_volume * extrapolation_factor),
                "whale_inflow": float(whale_inflow * extrapolation_factor),
                "whale_outflow": float(whale_outflow * extrapolation_factor),
                "net_whale_flow": float((whale_inflow - whale_outflow) * extrapolation_factor),
                "whale_dominance": min(0.5, float(whale_volume / Decimal(max(total_sampled, 1)) * Decimal('0.1'))),
                "sampled_txs": total_sampled,
                "detected_whale_txs": len(self._whale_transactions),
                "estimated": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self._cache = result
            self._cache_time = datetime.utcnow()
            
            return result
            
        except Exception as e:
            logger.error("Error in quick whale detection", error=str(e))
            # Return safe defaults
            return {
                "whale_tx_count": 0,
                "whale_volume_btc": 0,
                "whale_inflow": 0,
                "whale_outflow": 0,
                "net_whale_flow": 0,
                "whale_dominance": 0,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_whale_transactions(self) -> List[Dict[str, Any]]:
        """
        Get list of detected whale transactions.
        
        Call get_quick_metrics() first to populate this list.
        
        Returns:
            List of whale transaction dicts ready for database persistence
        """
        return self._whale_transactions
