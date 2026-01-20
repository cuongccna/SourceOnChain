"""Kill switch and safety control system for OnChain API."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from onchain_api.schemas.models import SignalStatus


class KillSwitchReason(Enum):
    """Kill switch activation reasons."""
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"
    INVARIANTS_FAILED = "invariants_failed"
    MISSING_BLOCK_DATA = "missing_block_data"
    ABNORMAL_SIGNAL_CONFLICT = "abnormal_signal_conflict"
    PIPELINE_LAG_EXCESSIVE = "pipeline_lag_excessive"
    DATA_COMPLETENESS_LOW = "data_completeness_low"
    VERIFICATION_FAILED = "verification_failed"
    SYSTEM_RESOURCE_CRITICAL = "system_resource_critical"
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    CALCULATION_TIMEOUT = "calculation_timeout"
    ANOMALY_THRESHOLD_EXCEEDED = "anomaly_threshold_exceeded"
    MANUAL_OVERRIDE = "manual_override"


@dataclass
class KillSwitchConfig:
    """Kill switch configuration parameters."""
    
    # Confidence thresholds
    min_confidence_ok: float = 0.70
    min_confidence_degraded: float = 0.50
    min_confidence_blocked: float = 0.30
    
    # Data quality thresholds
    min_data_completeness_ok: float = 0.90
    min_data_completeness_degraded: float = 0.70
    min_data_completeness_blocked: float = 0.50
    
    # Pipeline lag thresholds (blocks)
    max_pipeline_lag_ok: int = 3
    max_pipeline_lag_degraded: int = 10
    max_pipeline_lag_blocked: int = 50
    
    # Signal conflict thresholds
    max_conflicting_signals_ok: int = 1
    max_conflicting_signals_degraded: int = 3
    max_conflicting_signals_blocked: int = 5
    
    # System resource thresholds
    max_memory_usage_percent: int = 85
    max_cpu_usage_percent: int = 90
    max_calculation_time_ms: int = 10000
    
    # Database health thresholds
    max_query_latency_ms: int = 5000
    min_connection_pool_available: float = 0.1
    
    # Anomaly detection thresholds
    max_anomaly_flags: int = 3
    max_verification_failures: int = 2
    
    # Time-based thresholds
    max_data_age_seconds: int = 3600  # 1 hour
    max_calculation_age_seconds: int = 1800  # 30 minutes


@dataclass
class KillSwitchState:
    """Current kill switch state."""
    
    status: SignalStatus
    active_switches: List[KillSwitchReason]
    block_reasons: List[str]
    degradation_reasons: List[str]
    last_check: datetime
    override_active: bool = False
    override_reason: Optional[str] = None
    override_expires: Optional[datetime] = None


class KillSwitchController:
    """Main kill switch controller for API safety."""
    
    def __init__(self, config: KillSwitchConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.state = KillSwitchState(
            status=SignalStatus.OK,
            active_switches=[],
            block_reasons=[],
            degradation_reasons=[],
            last_check=datetime.now()
        )
        
        # Manual override state
        self._manual_overrides: Dict[str, datetime] = {}
        
        self.logger.info("Kill switch controller initialized")
    
    def evaluate_signal_safety(self, signal_data: Dict[str, Any]) -> Tuple[SignalStatus, List[str]]:
        """
        Evaluate signal safety and determine status.
        
        Args:
            signal_data: Complete signal data including verification metrics
            
        Returns:
            Tuple of (status, reasons) where status is OK/DEGRADED/BLOCKED
        """
        self.logger.debug("Evaluating signal safety", extra={"signal_timestamp": signal_data.get("timestamp")})
        
        block_reasons = []
        degradation_reasons = []
        
        # Check manual overrides first
        if self._check_manual_override():
            return SignalStatus.BLOCKED, ["manual_override_active"]
        
        # 1. Confidence checks
        confidence = signal_data.get("confidence", 0.0)
        confidence_status, confidence_reasons = self._check_confidence_thresholds(confidence)
        
        if confidence_status == SignalStatus.BLOCKED:
            block_reasons.extend(confidence_reasons)
        elif confidence_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(confidence_reasons)
        
        # 2. Data quality checks
        verification = signal_data.get("verification", {})
        quality_status, quality_reasons = self._check_data_quality(verification)
        
        if quality_status == SignalStatus.BLOCKED:
            block_reasons.extend(quality_reasons)
        elif quality_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(quality_reasons)
        
        # 3. Pipeline health checks
        metadata = signal_data.get("metadata", {})
        pipeline_status, pipeline_reasons = self._check_pipeline_health(metadata)
        
        if pipeline_status == SignalStatus.BLOCKED:
            block_reasons.extend(pipeline_reasons)
        elif pipeline_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(pipeline_reasons)
        
        # 4. Signal conflict checks
        signals = signal_data.get("signals", {})
        conflict_status, conflict_reasons = self._check_signal_conflicts(signals)
        
        if conflict_status == SignalStatus.BLOCKED:
            block_reasons.extend(conflict_reasons)
        elif conflict_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(conflict_reasons)
        
        # 5. System resource checks
        resource_status, resource_reasons = self._check_system_resources()
        
        if resource_status == SignalStatus.BLOCKED:
            block_reasons.extend(resource_reasons)
        elif resource_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(resource_reasons)
        
        # 6. Verification checks
        verification_status, verification_reasons = self._check_verification_results(verification)
        
        if verification_status == SignalStatus.BLOCKED:
            block_reasons.extend(verification_reasons)
        elif verification_status == SignalStatus.DEGRADED:
            degradation_reasons.extend(verification_reasons)
        
        # Determine final status
        if block_reasons:
            final_status = SignalStatus.BLOCKED
            final_reasons = block_reasons
            self.logger.warning("Signal BLOCKED", extra={
                "reasons": block_reasons,
                "confidence": confidence,
                "timestamp": signal_data.get("timestamp")
            })
        elif degradation_reasons:
            final_status = SignalStatus.DEGRADED
            final_reasons = degradation_reasons
            self.logger.info("Signal DEGRADED", extra={
                "reasons": degradation_reasons,
                "confidence": confidence,
                "timestamp": signal_data.get("timestamp")
            })
        else:
            final_status = SignalStatus.OK
            final_reasons = []
            self.logger.debug("Signal OK", extra={
                "confidence": confidence,
                "timestamp": signal_data.get("timestamp")
            })
        
        # Update internal state
        self._update_state(final_status, block_reasons, degradation_reasons)
        
        return final_status, final_reasons
    
    def _check_confidence_thresholds(self, confidence: float) -> Tuple[SignalStatus, List[str]]:
        """Check confidence against thresholds."""
        
        reasons = []
        
        if confidence < self.config.min_confidence_blocked:
            reasons.append(f"confidence_{confidence:.3f}_below_blocked_threshold_{self.config.min_confidence_blocked}")
            return SignalStatus.BLOCKED, reasons
        elif confidence < self.config.min_confidence_degraded:
            reasons.append(f"confidence_{confidence:.3f}_below_degraded_threshold_{self.config.min_confidence_degraded}")
            return SignalStatus.DEGRADED, reasons
        elif confidence < self.config.min_confidence_ok:
            reasons.append(f"confidence_{confidence:.3f}_below_ok_threshold_{self.config.min_confidence_ok}")
            return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, reasons
    
    def _check_data_quality(self, verification: Dict[str, Any]) -> Tuple[SignalStatus, List[str]]:
        """Check data quality metrics."""
        
        reasons = []
        
        # Data completeness check
        data_completeness = verification.get("data_completeness", 0.0)
        
        if data_completeness < self.config.min_data_completeness_blocked:
            reasons.append(f"data_completeness_{data_completeness:.3f}_below_blocked_threshold")
            return SignalStatus.BLOCKED, reasons
        elif data_completeness < self.config.min_data_completeness_degraded:
            reasons.append(f"data_completeness_{data_completeness:.3f}_below_degraded_threshold")
            return SignalStatus.DEGRADED, reasons
        elif data_completeness < self.config.min_data_completeness_ok:
            reasons.append(f"data_completeness_{data_completeness:.3f}_below_ok_threshold")
            return SignalStatus.DEGRADED, reasons
        
        # Invariant checks
        if not verification.get("invariants_passed", False):
            reasons.append("invariant_tests_failed")
            return SignalStatus.BLOCKED, reasons
        
        # Determinism checks
        if not verification.get("deterministic", False):
            reasons.append("calculation_not_deterministic")
            return SignalStatus.BLOCKED, reasons
        
        # Stability checks
        stability_score = verification.get("stability_score", 0.0)
        if stability_score < 0.5:
            reasons.append(f"stability_score_{stability_score:.3f}_too_low")
            return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, reasons
    
    def _check_pipeline_health(self, metadata: Dict[str, Any]) -> Tuple[SignalStatus, List[str]]:
        """Check pipeline health metrics."""
        
        reasons = []
        
        # Pipeline lag check
        pipeline_lag = metadata.get("pipeline_lag_blocks", 0)
        
        if pipeline_lag > self.config.max_pipeline_lag_blocked:
            reasons.append(f"pipeline_lag_{pipeline_lag}_blocks_exceeds_blocked_threshold")
            return SignalStatus.BLOCKED, reasons
        elif pipeline_lag > self.config.max_pipeline_lag_degraded:
            reasons.append(f"pipeline_lag_{pipeline_lag}_blocks_exceeds_degraded_threshold")
            return SignalStatus.DEGRADED, reasons
        elif pipeline_lag > self.config.max_pipeline_lag_ok:
            reasons.append(f"pipeline_lag_{pipeline_lag}_blocks_exceeds_ok_threshold")
            return SignalStatus.DEGRADED, reasons
        
        # Data age check
        data_age = metadata.get("data_age_seconds", 0)
        if data_age > self.config.max_data_age_seconds:
            reasons.append(f"data_age_{data_age}_seconds_too_old")
            return SignalStatus.DEGRADED, reasons
        
        # Calculation time check
        calc_time = metadata.get("calculation_time_ms", 0)
        if calc_time > self.config.max_calculation_time_ms:
            reasons.append(f"calculation_time_{calc_time}ms_too_slow")
            return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, reasons
    
    def _check_signal_conflicts(self, signals: Dict[str, bool]) -> Tuple[SignalStatus, List[str]]:
        """Check for abnormal signal conflicts."""
        
        reasons = []
        
        # Define conflicting signal pairs
        conflict_pairs = [
            ("network_growth_signal", "network_congestion_signal"),
            ("smart_money_accumulation_signal", "smart_money_distribution_signal"),
            ("net_utxo_inflow_signal", "capital_concentration_signal")
        ]
        
        conflict_count = 0
        
        for signal_a, signal_b in conflict_pairs:
            if signals.get(signal_a, False) and signals.get(signal_b, False):
                conflict_count += 1
                reasons.append(f"conflicting_signals_{signal_a}_and_{signal_b}")
        
        if conflict_count > self.config.max_conflicting_signals_blocked:
            return SignalStatus.BLOCKED, reasons
        elif conflict_count > self.config.max_conflicting_signals_degraded:
            return SignalStatus.DEGRADED, reasons
        elif conflict_count > self.config.max_conflicting_signals_ok:
            return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, []
    
    def _check_system_resources(self) -> Tuple[SignalStatus, List[str]]:
        """Check system resource utilization."""
        
        reasons = []
        
        try:
            import psutil
            
            # Memory check
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > self.config.max_memory_usage_percent:
                reasons.append(f"memory_usage_{memory_percent}%_too_high")
                return SignalStatus.BLOCKED, reasons
            
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.config.max_cpu_usage_percent:
                reasons.append(f"cpu_usage_{cpu_percent}%_too_high")
                return SignalStatus.DEGRADED, reasons
            
        except ImportError:
            self.logger.warning("psutil not available for resource monitoring")
        except Exception as e:
            self.logger.error(f"Error checking system resources: {e}")
            reasons.append("system_resource_check_failed")
            return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, reasons
    
    def _check_verification_results(self, verification: Dict[str, Any]) -> Tuple[SignalStatus, List[str]]:
        """Check verification test results."""
        
        reasons = []
        
        # Anomaly flags check
        anomaly_flags = verification.get("anomaly_flags", [])
        if len(anomaly_flags) > self.config.max_anomaly_flags:
            reasons.append(f"anomaly_flags_{len(anomaly_flags)}_exceeds_threshold")
            return SignalStatus.BLOCKED, reasons
        elif len(anomaly_flags) > 0:
            reasons.append(f"anomaly_flags_detected_{len(anomaly_flags)}")
            return SignalStatus.DEGRADED, reasons
        
        # Verification test results
        tests_passed = verification.get("verification_tests_passed", 0)
        tests_total = verification.get("verification_tests_total", 0)
        
        if tests_total > 0:
            failure_count = tests_total - tests_passed
            if failure_count > self.config.max_verification_failures:
                reasons.append(f"verification_failures_{failure_count}_exceeds_threshold")
                return SignalStatus.BLOCKED, reasons
            elif failure_count > 0:
                reasons.append(f"verification_failures_{failure_count}_detected")
                return SignalStatus.DEGRADED, reasons
        
        return SignalStatus.OK, reasons
    
    def _check_manual_override(self) -> bool:
        """Check if manual override is active."""
        
        if self.state.override_active:
            if self.state.override_expires and datetime.now() > self.state.override_expires:
                self.state.override_active = False
                self.state.override_reason = None
                self.state.override_expires = None
                self.logger.info("Manual override expired")
                return False
            return True
        
        return False
    
    def _update_state(self, status: SignalStatus, block_reasons: List[str], 
                     degradation_reasons: List[str]):
        """Update internal kill switch state."""
        
        self.state.status = status
        self.state.block_reasons = block_reasons
        self.state.degradation_reasons = degradation_reasons
        self.state.last_check = datetime.now()
        
        # Update active switches
        self.state.active_switches = []
        
        for reason in block_reasons + degradation_reasons:
            if "confidence" in reason:
                self.state.active_switches.append(KillSwitchReason.CONFIDENCE_BELOW_THRESHOLD)
            elif "invariant" in reason:
                self.state.active_switches.append(KillSwitchReason.INVARIANTS_FAILED)
            elif "pipeline_lag" in reason:
                self.state.active_switches.append(KillSwitchReason.PIPELINE_LAG_EXCESSIVE)
            elif "data_completeness" in reason:
                self.state.active_switches.append(KillSwitchReason.DATA_COMPLETENESS_LOW)
            elif "conflicting" in reason:
                self.state.active_switches.append(KillSwitchReason.ABNORMAL_SIGNAL_CONFLICT)
            elif "verification" in reason:
                self.state.active_switches.append(KillSwitchReason.VERIFICATION_FAILED)
            elif "memory" in reason or "cpu" in reason:
                self.state.active_switches.append(KillSwitchReason.SYSTEM_RESOURCE_CRITICAL)
            elif "anomaly" in reason:
                self.state.active_switches.append(KillSwitchReason.ANOMALY_THRESHOLD_EXCEEDED)
    
    def activate_manual_override(self, reason: str, duration_minutes: int = 60):
        """Activate manual kill switch override."""
        
        self.state.override_active = True
        self.state.override_reason = reason
        self.state.override_expires = datetime.now() + timedelta(minutes=duration_minutes)
        
        self.logger.warning("Manual kill switch override activated", extra={
            "reason": reason,
            "duration_minutes": duration_minutes,
            "expires": self.state.override_expires
        })
    
    def deactivate_manual_override(self):
        """Deactivate manual kill switch override."""
        
        self.state.override_active = False
        self.state.override_reason = None
        self.state.override_expires = None
        
        self.logger.info("Manual kill switch override deactivated")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current kill switch status summary."""
        
        return {
            "status": self.state.status.value,
            "last_check": self.state.last_check.isoformat(),
            "active_switches": [switch.value for switch in self.state.active_switches],
            "block_reasons": self.state.block_reasons,
            "degradation_reasons": self.state.degradation_reasons,
            "manual_override": {
                "active": self.state.override_active,
                "reason": self.state.override_reason,
                "expires": self.state.override_expires.isoformat() if self.state.override_expires else None
            }
        }
    
    def update_config(self, new_config: KillSwitchConfig):
        """Update kill switch configuration."""
        
        old_config = self.config
        self.config = new_config
        
        self.logger.info("Kill switch configuration updated", extra={
            "old_min_confidence": old_config.min_confidence_ok,
            "new_min_confidence": new_config.min_confidence_ok
        })


class FallbackController:
    """Controller for fallback signal generation."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_signals: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def get_fallback_signal(self, asset: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Get fallback signal when primary signal is blocked.
        
        Args:
            asset: Asset symbol
            timeframe: Signal timeframe
            
        Returns:
            Fallback signal data or None if unavailable
        """
        cache_key = f"{asset}_{timeframe}"
        
        # Check if we have cached fallback data
        if cache_key in self._cached_signals:
            cache_age = datetime.now() - self._cache_timestamps[cache_key]
            
            # Use cached data if less than 1 hour old
            if cache_age.total_seconds() < 3600:
                fallback_signal = self._cached_signals[cache_key].copy()
                fallback_signal.update({
                    "status": SignalStatus.DEGRADED,
                    "fallback_mode": True,
                    "fallback_reason": "primary_signal_blocked",
                    "fallback_age_seconds": int(cache_age.total_seconds())
                })
                
                self.logger.info("Returning cached fallback signal", extra={
                    "asset": asset,
                    "timeframe": timeframe,
                    "cache_age_seconds": int(cache_age.total_seconds())
                })
                
                return fallback_signal
        
        # No suitable fallback available
        self.logger.warning("No fallback signal available", extra={
            "asset": asset,
            "timeframe": timeframe
        })
        
        return None
    
    def cache_signal_for_fallback(self, asset: str, timeframe: str, signal_data: Dict[str, Any]):
        """Cache a good signal for potential fallback use."""
        
        # Only cache signals with high confidence and OK status
        if (signal_data.get("confidence", 0) >= 0.8 and 
            signal_data.get("status") == SignalStatus.OK):
            
            cache_key = f"{asset}_{timeframe}"
            self._cached_signals[cache_key] = signal_data.copy()
            self._cache_timestamps[cache_key] = datetime.now()
            
            self.logger.debug("Signal cached for fallback", extra={
                "asset": asset,
                "timeframe": timeframe,
                "confidence": signal_data.get("confidence")
            })
    
    def clear_fallback_cache(self, asset: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear fallback cache."""
        
        if asset and timeframe:
            cache_key = f"{asset}_{timeframe}"
            self._cached_signals.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
        else:
            self._cached_signals.clear()
            self._cache_timestamps.clear()
        
        self.logger.info("Fallback cache cleared", extra={
            "asset": asset,
            "timeframe": timeframe
        })