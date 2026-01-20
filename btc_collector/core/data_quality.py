"""
Data Quality & Verification Layer.

Quy tắc sống còn:
1. Không coi RPC/mempool là truth tuyệt đối
2. Phải có completeness score
3. Lag detection
4. BLOCK state

Architecture:
[ Ethereum RPC ] ──┐
                   ├─> On-chain Collector
[ mempool.space ] ─┘
                         ↓
                 Normalize & Verify  <-- THIS MODULE
                         ↓
                  Signal + Confidence
                         ↓
                   BotTrading
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import hashlib
import json

import structlog

logger = structlog.get_logger(__name__)


# ============================================================
# Enums & Constants
# ============================================================

class DataState(str, Enum):
    """System state based on data quality."""
    ACTIVE = "ACTIVE"       # Full confidence, use normally
    DEGRADED = "DEGRADED"   # Reduced confidence, use with caution
    BLOCKED = "BLOCKED"     # Do NOT use for trading decisions


class DataSource(str, Enum):
    """Supported data sources."""
    MEMPOOL_SPACE = "mempool_space"
    BLOCKCHAIN_INFO = "blockchain_info"
    BLOCKCYPHER = "blockcypher"
    BITCOIN_RPC = "bitcoin_rpc"
    ETHEREUM_RPC = "ethereum_rpc"


# Thresholds from environment
COMPLETENESS_THRESHOLD = float(os.getenv('ONCHAIN_COMPLETENESS_THRESHOLD', 0.80))
STABILITY_THRESHOLD = float(os.getenv('ONCHAIN_STABILITY_THRESHOLD', 0.70))
MIN_CONFIDENCE = float(os.getenv('ONCHAIN_MIN_CONFIDENCE', 0.60))
MAX_DATA_AGE_HOURS = float(os.getenv('ONCHAIN_MAX_DATA_AGE_HOURS', 2.0))
MAX_CONFLICTING_SIGNALS = int(os.getenv('ONCHAIN_MAX_CONFLICTING_SIGNALS', 2))


# ============================================================
# Data Models
# ============================================================

@dataclass
class DataQualityMetrics:
    """Metrics for assessing data quality."""
    
    # Completeness (0-1): Do we have all required data?
    completeness_score: float = 1.0
    missing_fields: List[str] = field(default_factory=list)
    
    # Freshness: Is data recent enough?
    data_age_seconds: float = 0.0
    is_stale: bool = False
    last_update: Optional[datetime] = None
    
    # Consistency: Do sources agree?
    source_agreement: float = 1.0
    conflicting_sources: List[str] = field(default_factory=list)
    
    # Validity: Is data within expected ranges?
    validity_score: float = 1.0
    anomalies_detected: List[str] = field(default_factory=list)
    
    # Overall
    overall_quality: float = 1.0
    
    def calculate_overall(self) -> float:
        """Calculate overall quality score."""
        weights = {
            'completeness': 0.30,
            'freshness': 0.25,
            'consistency': 0.25,
            'validity': 0.20
        }
        
        freshness_score = 0.0 if self.is_stale else 1.0
        
        self.overall_quality = (
            weights['completeness'] * self.completeness_score +
            weights['freshness'] * freshness_score +
            weights['consistency'] * self.source_agreement +
            weights['validity'] * self.validity_score
        )
        
        return self.overall_quality
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "completeness_score": round(self.completeness_score, 4),
            "missing_fields": self.missing_fields,
            "data_age_seconds": round(self.data_age_seconds, 1),
            "is_stale": self.is_stale,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "source_agreement": round(self.source_agreement, 4),
            "conflicting_sources": self.conflicting_sources,
            "validity_score": round(self.validity_score, 4),
            "anomalies_detected": self.anomalies_detected,
            "overall_quality": round(self.overall_quality, 4)
        }


@dataclass
class VerificationResult:
    """Result of data verification."""
    
    # State determination
    state: DataState = DataState.ACTIVE
    block_reason: Optional[str] = None
    
    # Quality metrics
    quality: DataQualityMetrics = field(default_factory=DataQualityMetrics)
    
    # Invariants
    invariants_passed: bool = True
    failed_invariants: List[str] = field(default_factory=list)
    
    # Determinism check
    is_deterministic: bool = True
    data_hash: str = ""
    
    # Confidence adjustment
    confidence_multiplier: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "block_reason": self.block_reason,
            "quality": self.quality.to_dict(),
            "invariants_passed": self.invariants_passed,
            "failed_invariants": self.failed_invariants,
            "is_deterministic": self.is_deterministic,
            "data_hash": self.data_hash[:16] + "..." if len(self.data_hash) > 16 else self.data_hash,
            "confidence_multiplier": round(self.confidence_multiplier, 4)
        }


# ============================================================
# Data Quality Checker
# ============================================================

class DataQualityChecker:
    """
    Verifies data quality before use in trading decisions.
    
    CRITICAL: Never trust a single source absolutely!
    """
    
    # Required fields for different data types
    REQUIRED_BLOCKCHAIN_FIELDS = [
        'block_height', 'blocks_analyzed', 'total_transactions'
    ]
    
    REQUIRED_MEMPOOL_FIELDS = [
        'pending_txs', 'fastest_fee'
    ]
    
    REQUIRED_WHALE_FIELDS = [
        'whale_tx_count', 'whale_volume_btc', 'net_whale_flow', 'whale_dominance'
    ]
    
    # Valid ranges for sanity checks
    VALID_RANGES = {
        'block_height': (800000, 2000000),  # Reasonable BTC block range
        'total_transactions': (0, 100000),   # Per analysis period
        'pending_txs': (0, 1000000),         # Mempool size
        'fastest_fee': (1, 10000),           # sat/vB
        'whale_dominance': (0, 1),           # Ratio
        'onchain_score': (0, 100),           # Score range
        'confidence': (0, 1)                  # Confidence range
    }
    
    def __init__(self):
        self.last_data_hash: Optional[str] = None
        self.last_check_time: Optional[datetime] = None
        
        logger.info("DataQualityChecker initialized",
                   completeness_threshold=COMPLETENESS_THRESHOLD,
                   max_data_age_hours=MAX_DATA_AGE_HOURS)
    
    def check_completeness(self, data: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Check if all required fields are present.
        
        Returns:
            Tuple of (completeness_score, missing_fields)
        """
        missing = []
        total_required = 0
        present = 0
        
        # Check blockchain fields
        blockchain = data.get('blockchain', {})
        for field in self.REQUIRED_BLOCKCHAIN_FIELDS:
            total_required += 1
            if field in blockchain and blockchain[field] is not None:
                present += 1
            else:
                missing.append(f"blockchain.{field}")
        
        # Check mempool fields
        mempool = data.get('mempool', {})
        for field in self.REQUIRED_MEMPOOL_FIELDS:
            total_required += 1
            if field in mempool and mempool[field] is not None:
                present += 1
            else:
                missing.append(f"mempool.{field}")
        
        # Check whale fields
        whale = data.get('whale', {})
        for field in self.REQUIRED_WHALE_FIELDS:
            total_required += 1
            if field in whale and whale[field] is not None:
                present += 1
            else:
                missing.append(f"whale.{field}")
        
        score = present / total_required if total_required > 0 else 0.0
        
        return score, missing
    
    def check_freshness(self, data: Dict[str, Any], 
                       max_age_hours: float = None) -> Tuple[float, bool]:
        """
        Check if data is fresh enough.
        
        Returns:
            Tuple of (age_seconds, is_stale)
        """
        max_age = max_age_hours or MAX_DATA_AGE_HOURS
        max_age_seconds = max_age * 3600
        
        # Get timestamp from data
        timestamp_str = data.get('timestamp') or data.get('whale', {}).get('timestamp')
        
        if timestamp_str:
            try:
                if isinstance(timestamp_str, str):
                    # Parse ISO format
                    timestamp_str = timestamp_str.replace('Z', '+00:00')
                    data_time = datetime.fromisoformat(timestamp_str)
                else:
                    data_time = timestamp_str
                
                # Make timezone-naive for comparison
                if data_time.tzinfo:
                    data_time = data_time.replace(tzinfo=None)
                
                age = (datetime.utcnow() - data_time).total_seconds()
                is_stale = age > max_age_seconds
                
                return age, is_stale
                
            except Exception as e:
                logger.warning("Failed to parse timestamp", error=str(e))
        
        # No timestamp = assume stale
        return max_age_seconds + 1, True
    
    def check_validity(self, data: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Check if values are within expected ranges.
        
        Returns:
            Tuple of (validity_score, anomalies)
        """
        anomalies = []
        total_checks = 0
        passed = 0
        
        def check_range(value: Any, field: str, path: str):
            nonlocal total_checks, passed
            
            if field not in self.VALID_RANGES:
                return
            
            total_checks += 1
            min_val, max_val = self.VALID_RANGES[field]
            
            try:
                val = float(value)
                if min_val <= val <= max_val:
                    passed += 1
                else:
                    anomalies.append(f"{path}: {val} outside [{min_val}, {max_val}]")
            except (TypeError, ValueError):
                anomalies.append(f"{path}: invalid type {type(value)}")
        
        # Check blockchain
        blockchain = data.get('blockchain', {})
        for field in ['block_height', 'total_transactions']:
            if field in blockchain:
                check_range(blockchain[field], field, f"blockchain.{field}")
        
        # Check mempool
        mempool = data.get('mempool', {})
        for field in ['pending_txs', 'fastest_fee']:
            if field in mempool:
                check_range(mempool[field], field, f"mempool.{field}")
        
        # Check whale
        whale = data.get('whale', {})
        if 'whale_dominance' in whale:
            check_range(whale['whale_dominance'], 'whale_dominance', 'whale.whale_dominance')
        
        score = passed / total_checks if total_checks > 0 else 1.0
        
        return score, anomalies
    
    def compute_data_hash(self, data: Dict[str, Any]) -> str:
        """
        Compute deterministic hash of data for verification.
        """
        # Serialize with sorted keys for determinism
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def verify(self, data: Dict[str, Any], 
              signals: Optional[Dict[str, bool]] = None) -> VerificationResult:
        """
        Perform full verification of data quality.
        
        This is the main entry point for the verification layer.
        
        CRITICAL RULE: If verification fails, state MUST be BLOCKED!
        """
        result = VerificationResult()
        result.quality = DataQualityMetrics()
        
        logger.debug("Starting data verification")
        
        # 1. Check completeness
        completeness, missing = self.check_completeness(data)
        result.quality.completeness_score = completeness
        result.quality.missing_fields = missing
        
        if completeness < COMPLETENESS_THRESHOLD:
            result.failed_invariants.append(
                f"completeness ({completeness:.2f}) < threshold ({COMPLETENESS_THRESHOLD})"
            )
        
        # 2. Check freshness (LAG DETECTION)
        age, is_stale = self.check_freshness(data)
        result.quality.data_age_seconds = age
        result.quality.is_stale = is_stale
        result.quality.last_update = datetime.utcnow()
        
        if is_stale:
            result.failed_invariants.append(
                f"data is stale (age: {age:.0f}s > max: {MAX_DATA_AGE_HOURS * 3600:.0f}s)"
            )
        
        # 3. Check validity
        validity, anomalies = self.check_validity(data)
        result.quality.validity_score = validity
        result.quality.anomalies_detected = anomalies
        
        if anomalies:
            result.failed_invariants.append(
                f"anomalies detected: {len(anomalies)}"
            )
        
        # 4. Calculate overall quality
        result.quality.calculate_overall()
        
        # 5. Compute data hash for determinism check
        result.data_hash = self.compute_data_hash(data)
        
        # Check determinism (same input should produce same hash)
        if self.last_data_hash and result.data_hash == self.last_data_hash:
            # Data hasn't changed - might indicate stuck source
            time_since_last = (datetime.utcnow() - self.last_check_time).total_seconds() if self.last_check_time else 0
            if time_since_last > 600:  # 10 minutes
                result.is_deterministic = False
                result.failed_invariants.append("data unchanged for >10 minutes")
        
        self.last_data_hash = result.data_hash
        self.last_check_time = datetime.utcnow()
        
        # 6. Check signal conflicts if provided
        if signals:
            conflicts = self._check_signal_conflicts(signals)
            if conflicts > MAX_CONFLICTING_SIGNALS:
                result.failed_invariants.append(
                    f"too many conflicting signals: {conflicts} > {MAX_CONFLICTING_SIGNALS}"
                )
        
        # 7. Determine invariants status
        result.invariants_passed = len(result.failed_invariants) == 0
        
        # 8. DETERMINE STATE (CRITICAL!)
        result.state = self._determine_state(result)
        
        # 9. Calculate confidence multiplier
        result.confidence_multiplier = self._calculate_confidence_multiplier(result)
        
        logger.info("Verification complete",
                   state=result.state.value,
                   quality=result.quality.overall_quality,
                   invariants_passed=result.invariants_passed)
        
        return result
    
    def _check_signal_conflicts(self, signals: Dict[str, bool]) -> int:
        """Count conflicting signals."""
        conflicts = 0
        
        # Accumulation vs Distribution conflict
        if signals.get('smart_money_accumulation') and signals.get('distribution_risk'):
            conflicts += 1
        
        # Network growth vs congestion (if we had it)
        # Add more conflict checks as needed
        
        return conflicts
    
    def _determine_state(self, result: VerificationResult) -> DataState:
        """
        Determine system state based on verification results.
        
        CRITICAL: This determines if data can be used for trading!
        """
        quality = result.quality
        
        # BLOCK conditions (DO NOT USE DATA)
        if quality.completeness_score < 0.5:
            result.block_reason = "Critical data missing (completeness < 50%)"
            return DataState.BLOCKED
        
        if quality.is_stale and quality.data_age_seconds > MAX_DATA_AGE_HOURS * 3600 * 2:
            result.block_reason = "Data too old (>2x max age)"
            return DataState.BLOCKED
        
        if not result.is_deterministic:
            result.block_reason = "Non-deterministic data source"
            return DataState.BLOCKED
        
        if len(result.quality.anomalies_detected) >= 3:
            result.block_reason = "Multiple anomalies detected"
            return DataState.BLOCKED
        
        # DEGRADED conditions (USE WITH CAUTION)
        if not result.invariants_passed:
            return DataState.DEGRADED
        
        if quality.overall_quality < STABILITY_THRESHOLD:
            return DataState.DEGRADED
        
        if quality.is_stale:
            return DataState.DEGRADED
        
        # ACTIVE (NORMAL OPERATION)
        return DataState.ACTIVE
    
    def _calculate_confidence_multiplier(self, result: VerificationResult) -> float:
        """
        Calculate how much to reduce confidence based on data quality.
        """
        if result.state == DataState.BLOCKED:
            return 0.0  # No confidence in blocked data
        
        if result.state == DataState.DEGRADED:
            return max(0.3, result.quality.overall_quality * 0.5)
        
        # Active state - use quality score
        return min(1.0, result.quality.overall_quality)


# ============================================================
# Multi-Source Verifier
# ============================================================

class MultiSourceVerifier:
    """
    Verifies data across multiple sources.
    
    RULE: Never trust a single source absolutely!
    """
    
    def __init__(self):
        self.source_data: Dict[DataSource, Dict[str, Any]] = {}
        self.source_timestamps: Dict[DataSource, datetime] = {}
        
        logger.info("MultiSourceVerifier initialized")
    
    def add_source_data(self, source: DataSource, data: Dict[str, Any]):
        """Add data from a source."""
        self.source_data[source] = data
        self.source_timestamps[source] = datetime.utcnow()
    
    def verify_cross_source(self) -> Tuple[float, List[str]]:
        """
        Cross-validate data between sources.
        
        Returns:
            Tuple of (agreement_score, conflicting_sources)
        """
        if len(self.source_data) < 2:
            # Can't cross-validate with single source
            return 0.8, ["single_source_only"]
        
        conflicts = []
        agreements = 0
        total_checks = 0
        
        # Compare block heights across sources
        heights = {}
        for source, data in self.source_data.items():
            if 'blockchain' in data and 'block_height' in data['blockchain']:
                heights[source] = data['blockchain']['block_height']
        
        if len(heights) >= 2:
            height_values = list(heights.values())
            max_diff = max(height_values) - min(height_values)
            total_checks += 1
            
            if max_diff <= 2:  # Allow 2 block difference
                agreements += 1
            else:
                conflicts.append(f"block_height_mismatch: {heights}")
        
        # Compare pending transactions
        pending = {}
        for source, data in self.source_data.items():
            if 'mempool' in data and 'pending_txs' in data['mempool']:
                pending[source] = data['mempool']['pending_txs']
        
        if len(pending) >= 2:
            pending_values = list(pending.values())
            avg = sum(pending_values) / len(pending_values)
            max_deviation = max(abs(v - avg) / avg for v in pending_values) if avg > 0 else 0
            total_checks += 1
            
            if max_deviation <= 0.2:  # Allow 20% difference
                agreements += 1
            else:
                conflicts.append(f"pending_txs_mismatch: {pending}")
        
        agreement_score = agreements / total_checks if total_checks > 0 else 0.8
        
        return agreement_score, conflicts
    
    def get_consensus_data(self) -> Dict[str, Any]:
        """
        Get consensus data from multiple sources.
        
        Uses median for numeric values when sources disagree.
        """
        if not self.source_data:
            return {}
        
        if len(self.source_data) == 1:
            return list(self.source_data.values())[0]
        
        # For now, return first source (in production, implement median logic)
        return list(self.source_data.values())[0]


# ============================================================
# Convenience Functions
# ============================================================

_quality_checker: Optional[DataQualityChecker] = None


def get_quality_checker() -> DataQualityChecker:
    """Get or create quality checker singleton."""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = DataQualityChecker()
    return _quality_checker


def verify_data(data: Dict[str, Any], 
               signals: Optional[Dict[str, bool]] = None) -> VerificationResult:
    """
    Convenience function to verify data quality.
    
    Usage:
        result = verify_data(metrics, signals)
        if result.state == DataState.BLOCKED:
            # DO NOT USE DATA
        elif result.state == DataState.DEGRADED:
            # Use with reduced weight
        else:
            # Normal operation
    """
    checker = get_quality_checker()
    return checker.verify(data, signals)
