"""
Unified Pipeline - Normalize, Verify, Generate Signals.

Architecture:
[ Bitcoin RPC / mempool.space ] ──┐
                                  ├─> On-chain Collector
[ Ethereum RPC / External APIs ] ─┘
                                        ↓
                                Normalize & Verify  
                                        ↓
                                 Signal + Confidence
                                        ↓
                                    BotTrading

This module orchestrates the entire data flow.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

import structlog

# Internal imports
from .data_quality import (
    DataQualityChecker, 
    VerificationResult, 
    DataState,
    verify_data
)
from .data_provider import DataProvider
from .whale_analyzer import QuickWhaleDetector

logger = structlog.get_logger(__name__)


# ============================================================
# Normalized Data Models
# ============================================================

@dataclass 
class NormalizedBlockchainData:
    """Normalized blockchain metrics."""
    
    block_height: int = 0
    blocks_analyzed: int = 0
    total_transactions: int = 0
    avg_tx_per_block: float = 0.0
    total_volume_btc: float = 0.0
    avg_volume_per_block: float = 0.0
    
    # Source tracking
    source: str = "unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_height": self.block_height,
            "blocks_analyzed": self.blocks_analyzed,
            "total_transactions": self.total_transactions,
            "avg_tx_per_block": round(self.avg_tx_per_block, 2),
            "total_volume_btc": round(self.total_volume_btc, 2),
            "avg_volume_per_block": round(self.avg_volume_per_block, 2),
            "source": self.source
        }


@dataclass
class NormalizedMempoolData:
    """Normalized mempool metrics."""
    
    pending_txs: int = 0
    total_fees_btc: float = 0.0
    fastest_fee: int = 0
    half_hour_fee: int = 0
    hour_fee: int = 0
    economy_fee: int = 0
    mempool_size_mb: float = 0.0
    congestion_level: str = "normal"
    
    # Source tracking
    source: str = "unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending_txs": self.pending_txs,
            "total_fees_btc": round(self.total_fees_btc, 8),
            "fastest_fee": self.fastest_fee,
            "half_hour_fee": self.half_hour_fee,
            "hour_fee": self.hour_fee,
            "economy_fee": self.economy_fee,
            "mempool_size_mb": round(self.mempool_size_mb, 2),
            "congestion_level": self.congestion_level,
            "source": self.source
        }


@dataclass
class NormalizedWhaleData:
    """Normalized whale activity metrics."""
    
    whale_tx_count: int = 0
    whale_volume_btc: float = 0.0
    net_whale_flow: float = 0.0
    whale_dominance: float = 0.0
    largest_tx_btc: float = 0.0
    flow_direction: str = "neutral"
    whale_sentiment: str = "neutral"
    
    # Tier breakdown
    tier_breakdown: Dict[str, int] = field(default_factory=dict)
    
    # Source tracking
    source: str = "unknown"
    timestamp: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "whale_tx_count": self.whale_tx_count,
            "whale_volume_btc": round(self.whale_volume_btc, 4),
            "net_whale_flow": round(self.net_whale_flow, 4),
            "whale_dominance": round(self.whale_dominance, 4),
            "largest_tx_btc": round(self.largest_tx_btc, 4),
            "flow_direction": self.flow_direction,
            "whale_sentiment": self.whale_sentiment,
            "tier_breakdown": self.tier_breakdown,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


# ============================================================
# Signal Generation
# ============================================================

class SignalEngine:
    """
    Generate trading signals from normalized data.
    
    Signals are boolean flags with associated weights.
    Final score = sum(signal_value * weight)
    """
    
    # Signal weights (positive = bullish, negative = bearish)
    SIGNAL_WEIGHTS = {
        # Bullish signals
        'smart_money_accumulation': 30,
        'network_growth': 20,
        'exchange_outflow': 25,
        'whale_accumulation': 35,
        'low_fees_activity': 10,
        
        # Bearish signals  
        'distribution_risk': -40,
        'exchange_inflow': -25,
        'high_congestion': -15,
        'whale_distribution': -35,
        'declining_activity': -20
    }
    
    def __init__(self):
        self.base_confidence = 0.75
        logger.info("SignalEngine initialized")
    
    def generate_signals(self, 
                        blockchain: NormalizedBlockchainData,
                        mempool: NormalizedMempoolData,
                        whale: NormalizedWhaleData) -> Dict[str, bool]:
        """Generate boolean signals from normalized data."""
        
        signals = {}
        
        # === Whale-based signals ===
        
        # Smart money accumulation (large net inflow)
        signals['smart_money_accumulation'] = (
            whale.net_whale_flow > 1000 and  # >1000 BTC net inflow
            whale.flow_direction == "inflow"
        )
        
        # Distribution risk (large net outflow)
        signals['distribution_risk'] = (
            whale.net_whale_flow < -1000 or  # >1000 BTC net outflow
            whale.flow_direction == "outflow"
        )
        
        # Whale accumulation
        signals['whale_accumulation'] = (
            whale.whale_sentiment in ["bullish", "strongly_bullish"] and
            whale.whale_dominance > 0.05
        )
        
        # Whale distribution
        signals['whale_distribution'] = (
            whale.whale_sentiment in ["bearish", "strongly_bearish"] and
            whale.whale_dominance > 0.05
        )
        
        # === Network activity signals ===
        
        # Network growth (high transaction count)
        signals['network_growth'] = (
            blockchain.avg_tx_per_block > 2500
        )
        
        # Declining activity
        signals['declining_activity'] = (
            blockchain.avg_tx_per_block < 1500
        )
        
        # === Mempool/fee signals ===
        
        # Low fees = less competition = possible accumulation phase
        signals['low_fees_activity'] = (
            mempool.fastest_fee < 20 and
            mempool.congestion_level == "low"
        )
        
        # High congestion = lots of activity (can be bullish or bearish)
        signals['high_congestion'] = (
            mempool.congestion_level in ["high", "very_high"] or
            mempool.fastest_fee > 100
        )
        
        # Exchange flow signals (placeholder - would need exchange data)
        signals['exchange_outflow'] = False  # TODO: implement with exchange data
        signals['exchange_inflow'] = False   # TODO: implement with exchange data
        
        logger.debug("Signals generated", 
                    active_signals=[k for k, v in signals.items() if v])
        
        return signals
    
    def calculate_score(self, signals: Dict[str, bool]) -> Tuple[int, str]:
        """
        Calculate final score from signals.
        
        Returns:
            Tuple of (score 0-100, bias)
        """
        # Start at neutral (50)
        raw_score = 50
        
        for signal_name, is_active in signals.items():
            if is_active and signal_name in self.SIGNAL_WEIGHTS:
                raw_score += self.SIGNAL_WEIGHTS[signal_name]
        
        # Clamp to 0-100
        final_score = max(0, min(100, raw_score))
        
        # Determine bias
        if final_score >= 65:
            bias = "positive"
        elif final_score <= 35:
            bias = "negative"
        else:
            bias = "neutral"
        
        return final_score, bias
    
    def calculate_confidence(self, 
                            signals: Dict[str, bool],
                            verification: VerificationResult) -> float:
        """
        Calculate confidence in the signals.
        
        Factors:
        - Data quality (from verification)
        - Number of active signals (more = more confidence)
        - Signal conflicts (reduce confidence)
        """
        # Start with base confidence
        confidence = self.base_confidence
        
        # Apply data quality multiplier
        confidence *= verification.confidence_multiplier
        
        # Boost for more active signals (more data = more confidence)
        active_signals = sum(1 for v in signals.values() if v)
        if active_signals >= 3:
            confidence *= 1.1
        elif active_signals >= 5:
            confidence *= 1.2
        
        # Reduce for conflicts
        if signals.get('smart_money_accumulation') and signals.get('distribution_risk'):
            confidence *= 0.7
        
        if signals.get('whale_accumulation') and signals.get('whale_distribution'):
            confidence *= 0.7
        
        # Reduce if data quality is poor
        if verification.state == DataState.DEGRADED:
            confidence *= 0.8
        
        # Cap at 1.0
        return min(1.0, confidence)


# ============================================================
# Main Pipeline
# ============================================================

class OnChainPipeline:
    """
    Main pipeline for on-chain data processing.
    
    Flow:
    1. Collect data from sources
    2. Normalize data
    3. Verify data quality
    4. Generate signals
    5. Return BotTrading-ready output
    """
    
    def __init__(self, data_provider: Optional[DataProvider] = None):
        self.data_provider = data_provider or DataProvider()
        self.signal_engine = SignalEngine()
        self.quality_checker = DataQualityChecker()
        self.whale_detector = QuickWhaleDetector()
        
        logger.info("OnChainPipeline initialized")
    
    async def collect_data(self) -> Dict[str, Any]:
        """Collect raw data from all sources."""
        
        # Get blockchain data
        blockchain_raw = await self.data_provider.get_blockchain_data()
        
        # Get mempool data  
        mempool_raw = await self.data_provider.get_mempool_data()
        
        # Get whale data
        whale_raw = await self.whale_detector.detect()
        
        return {
            'blockchain_raw': blockchain_raw,
            'mempool_raw': mempool_raw,
            'whale_raw': whale_raw,
            'collected_at': datetime.utcnow().isoformat()
        }
    
    def normalize_blockchain(self, raw: Dict[str, Any]) -> NormalizedBlockchainData:
        """Normalize blockchain data."""
        
        normalized = NormalizedBlockchainData()
        
        if not raw:
            return normalized
        
        normalized.block_height = raw.get('height', 0)
        normalized.blocks_analyzed = 1
        
        # Handle different data formats
        if 'n_tx' in raw:
            normalized.total_transactions = raw['n_tx']
        elif 'tx_count' in raw:
            normalized.total_transactions = raw['tx_count']
        
        normalized.avg_tx_per_block = normalized.total_transactions
        
        # Volume - might be in different units
        if 'total_volume_btc' in raw:
            normalized.total_volume_btc = raw['total_volume_btc']
        
        normalized.source = "mempool_space"
        normalized.raw_data = raw
        
        return normalized
    
    def normalize_mempool(self, raw: Dict[str, Any]) -> NormalizedMempoolData:
        """Normalize mempool data."""
        
        normalized = NormalizedMempoolData()
        
        if not raw:
            return normalized
        
        mempool_info = raw.get('mempool_info', raw)
        fees = raw.get('recommended_fees', raw)
        
        normalized.pending_txs = mempool_info.get('count', 0)
        normalized.mempool_size_mb = mempool_info.get('vsize', 0) / 1_000_000
        
        # Fee rates
        normalized.fastest_fee = fees.get('fastestFee', 0)
        normalized.half_hour_fee = fees.get('halfHourFee', 0)
        normalized.hour_fee = fees.get('hourFee', 0)
        normalized.economy_fee = fees.get('economyFee', 0)
        
        # Determine congestion
        if normalized.fastest_fee > 100:
            normalized.congestion_level = "very_high"
        elif normalized.fastest_fee > 50:
            normalized.congestion_level = "high"
        elif normalized.fastest_fee > 20:
            normalized.congestion_level = "normal"
        else:
            normalized.congestion_level = "low"
        
        normalized.source = "mempool_space"
        normalized.raw_data = raw
        
        return normalized
    
    def normalize_whale(self, raw: Dict[str, Any]) -> NormalizedWhaleData:
        """Normalize whale data."""
        
        normalized = NormalizedWhaleData()
        
        if not raw:
            return normalized
        
        normalized.whale_tx_count = raw.get('whale_tx_count', 0)
        normalized.whale_volume_btc = raw.get('total_whale_volume_btc', 0)
        normalized.net_whale_flow = raw.get('net_whale_flow_btc', 0)
        normalized.whale_dominance = raw.get('whale_dominance', 0)
        normalized.largest_tx_btc = raw.get('largest_tx_btc', 0)
        
        # Flow direction
        if normalized.net_whale_flow > 500:
            normalized.flow_direction = "inflow"
        elif normalized.net_whale_flow < -500:
            normalized.flow_direction = "outflow"
        else:
            normalized.flow_direction = "neutral"
        
        # Sentiment from flow
        if normalized.net_whale_flow > 5000:
            normalized.whale_sentiment = "strongly_bullish"
        elif normalized.net_whale_flow > 1000:
            normalized.whale_sentiment = "bullish"
        elif normalized.net_whale_flow < -5000:
            normalized.whale_sentiment = "strongly_bearish"
        elif normalized.net_whale_flow < -1000:
            normalized.whale_sentiment = "bearish"
        else:
            normalized.whale_sentiment = "neutral"
        
        # Tier breakdown
        normalized.tier_breakdown = raw.get('tier_breakdown', {})
        
        normalized.source = "mempool_space"
        normalized.timestamp = datetime.utcnow()
        normalized.raw_data = raw
        
        return normalized
    
    async def run(self) -> Dict[str, Any]:
        """
        Run the complete pipeline.
        
        Returns BotTrading-ready output with:
        - data state (ACTIVE/DEGRADED/BLOCKED)
        - normalized metrics
        - signals
        - score and confidence
        - quality metrics
        """
        
        logger.info("Starting pipeline run")
        start_time = datetime.utcnow()
        
        try:
            # 1. Collect raw data
            raw_data = await self.collect_data()
            
            # 2. Normalize data
            blockchain = self.normalize_blockchain(raw_data.get('blockchain_raw', {}))
            mempool = self.normalize_mempool(raw_data.get('mempool_raw', {}))
            whale = self.normalize_whale(raw_data.get('whale_raw', {}))
            
            # 3. Prepare data for verification
            verification_data = {
                'blockchain': blockchain.to_dict(),
                'mempool': mempool.to_dict(),
                'whale': whale.to_dict(),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # 4. Generate signals (preliminary)
            signals = self.signal_engine.generate_signals(blockchain, mempool, whale)
            
            # 5. Verify data quality
            verification = self.quality_checker.verify(verification_data, signals)
            
            # 6. Calculate score and confidence
            score, bias = self.signal_engine.calculate_score(signals)
            confidence = self.signal_engine.calculate_confidence(signals, verification)
            
            # 7. Build response
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                # State (CRITICAL for BotTrading)
                "state": verification.state.value,
                "block_reason": verification.block_reason,
                
                # Timing
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "processing_time_seconds": round(processing_time, 3),
                
                # Quality metrics
                "quality": verification.quality.to_dict(),
                "verification": {
                    "invariants_passed": verification.invariants_passed,
                    "failed_invariants": verification.failed_invariants,
                    "data_hash": verification.data_hash[:16] + "..."
                },
                
                # Normalized data
                "metrics": {
                    "blockchain": blockchain.to_dict(),
                    "mempool": mempool.to_dict(),
                    "whale": whale.to_dict()
                },
                
                # Signals
                "signals": {
                    "active": [k for k, v in signals.items() if v],
                    "all": signals
                },
                
                # Final output for BotTrading
                "score": score,
                "bias": bias,
                "confidence": round(confidence, 4),
                
                # Usage recommendation
                "usage": self._get_usage_recommendation(verification.state, confidence)
            }
            
            logger.info("Pipeline run complete",
                       state=verification.state.value,
                       score=score,
                       confidence=confidence,
                       processing_time=processing_time)
            
            return result
            
        except Exception as e:
            logger.exception("Pipeline error", error=str(e))
            
            return {
                "state": DataState.BLOCKED.value,
                "block_reason": f"Pipeline error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "score": 50,
                "bias": "neutral",
                "confidence": 0.0,
                "usage": {
                    "can_use": False,
                    "weight_multiplier": 0.0,
                    "recommendation": "DO NOT USE - Pipeline error"
                }
            }
    
    def _get_usage_recommendation(self, state: DataState, confidence: float) -> Dict[str, Any]:
        """Get usage recommendation for BotTrading."""
        
        if state == DataState.BLOCKED:
            return {
                "can_use": False,
                "weight_multiplier": 0.0,
                "recommendation": "DO NOT USE - Data quality issues"
            }
        
        if state == DataState.DEGRADED:
            weight = float(os.getenv('ONCHAIN_DEGRADED_WEIGHT', 0.3))
            return {
                "can_use": True,
                "weight_multiplier": weight,
                "recommendation": f"Use with reduced weight ({weight}x)"
            }
        
        # Active state
        weight = float(os.getenv('ONCHAIN_NORMAL_WEIGHT', 1.0))
        return {
            "can_use": True,
            "weight_multiplier": weight * confidence,
            "recommendation": "Normal operation"
        }


# ============================================================
# Convenience function
# ============================================================

async def run_pipeline() -> Dict[str, Any]:
    """Convenience function to run the pipeline."""
    pipeline = OnChainPipeline()
    return await pipeline.run()
