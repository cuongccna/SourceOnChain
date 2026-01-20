"""Kill Switch Controller for OnChain Intelligence Data Product."""

from typing import Dict, Any
import structlog

from config import ProductConfig


logger = structlog.get_logger(__name__)


class KillSwitchController:
    """
    Kill switch controller implementing mandatory state machine logic.
    
    BLOCKED conditions (hard rules):
    - invariants_passed == false
    - data_lag == true  
    - confidence < MIN_CONFIDENCE
    - deterministic == false
    
    DEGRADED conditions:
    - stability_score < STABILITY_THRESHOLD
    - data_completeness < COMPLETENESS_THRESHOLD
    - signal_conflict == true
    
    ACTIVE: All other cases
    """
    
    def __init__(self, config: ProductConfig):
        self.config = config
        self.logger = logger.bind(component="kill_switch")
    
    def evaluate_and_apply(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate context data and apply kill switch logic.
        
        Returns modified context data with state and usage_policy applied.
        """
        
        verification = context_data.get("verification", {})
        risk_flags = context_data.get("risk_flags", {})
        decision_context = context_data.get("decision_context", {})
        
        # Extract key values
        invariants_passed = verification.get("invariants_passed", False)
        deterministic = verification.get("deterministic", False)
        stability_score = verification.get("stability_score", 0.0)
        data_completeness = verification.get("data_completeness", 0.0)
        confidence = decision_context.get("confidence", 0.0)
        data_lag = risk_flags.get("data_lag", True)
        signal_conflict = risk_flags.get("signal_conflict", False)
        
        # Apply state machine logic
        state, usage_policy = self._determine_state_and_policy(
            invariants_passed=invariants_passed,
            deterministic=deterministic,
            stability_score=stability_score,
            data_completeness=data_completeness,
            confidence=confidence,
            data_lag=data_lag,
            signal_conflict=signal_conflict
        )
        
        # Apply blocking logic to decision context
        if state == "BLOCKED":
            decision_context["onchain_score"] = None
            # Keep bias and confidence for transparency
        
        # Build final response
        final_context = {
            "product": "onchain_intelligence",
            "version": "1.0.0",
            "asset": context_data.get("asset", "BTC"),
            "timeframe": context_data.get("timeframe", "1d"),
            "timestamp": context_data.get("timestamp"),
            "state": state,
            "decision_context": decision_context,
            "signals": context_data.get("signals", {}),
            "risk_flags": risk_flags,
            "verification": verification,
            "usage_policy": usage_policy
        }
        
        self.logger.info("Kill switch evaluation completed",
                        state=state,
                        allowed=usage_policy["allowed"],
                        recommended_weight=usage_policy["recommended_weight"])
        
        return final_context
    
    def _determine_state_and_policy(self,
                                   invariants_passed: bool,
                                   deterministic: bool,
                                   stability_score: float,
                                   data_completeness: float,
                                   confidence: float,
                                   data_lag: bool,
                                   signal_conflict: bool) -> tuple[str, Dict[str, Any]]:
        """
        Determine state and usage policy based on kill switch rules.
        
        Returns (state, usage_policy) tuple.
        """
        
        # BLOCKED conditions (mandatory hard rules)
        blocked_reasons = []
        
        if not invariants_passed:
            blocked_reasons.append("invariants_failed")
        
        if data_lag:
            blocked_reasons.append("data_lag_exceeded")
        
        if confidence < self.config.min_confidence:
            blocked_reasons.append(f"confidence_below_threshold_{self.config.min_confidence}")
        
        if not deterministic:
            blocked_reasons.append("non_deterministic_calculation")
        
        if blocked_reasons:
            self.logger.warning("Data BLOCKED", reasons=blocked_reasons)
            return "BLOCKED", {
                "allowed": False,
                "recommended_weight": 0.0,
                "notes": f"Data blocked: {', '.join(blocked_reasons)}"
            }
        
        # DEGRADED conditions
        degraded_reasons = []
        
        if stability_score < self.config.stability_threshold:
            degraded_reasons.append(f"stability_below_threshold_{self.config.stability_threshold}")
        
        if data_completeness < self.config.completeness_threshold:
            degraded_reasons.append(f"completeness_below_threshold_{self.config.completeness_threshold}")
        
        if signal_conflict:
            degraded_reasons.append("signal_conflicts_detected")
        
        if degraded_reasons:
            self.logger.info("Data DEGRADED", reasons=degraded_reasons)
            return "DEGRADED", {
                "allowed": True,
                "recommended_weight": self.config.degraded_weight,
                "notes": f"Data quality degraded: {', '.join(degraded_reasons)}"
            }
        
        # ACTIVE state
        self.logger.info("Data ACTIVE")
        return "ACTIVE", {
            "allowed": True,
            "recommended_weight": self.config.normal_weight,
            "notes": "Data quality acceptable for normal usage"
        }