"""Unit tests for Kill Switch Controller."""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import sys
sys.path.insert(0, 'd:/projects/OnChain/SourceOnChain/onchain_intel_product')

from kill_switch import KillSwitchController
from config import ProductConfig


class TestKillSwitchController:
    """Test suite for KillSwitchController."""
    
    @pytest.fixture
    def config(self):
        """Default test configuration."""
        config = MagicMock(spec=ProductConfig)
        config.min_confidence = 0.60
        config.stability_threshold = 0.70
        config.completeness_threshold = 0.80
        config.max_data_age_hours = 2.0
        config.max_conflicting_signals = 2
        config.normal_weight = 1.0
        config.degraded_weight = 0.3
        return config
    
    @pytest.fixture
    def kill_switch(self, config):
        """Kill switch controller instance."""
        return KillSwitchController(config)
    
    # ========================================================================
    # STATE MACHINE TESTS: ACTIVE STATE
    # ========================================================================
    
    def test_active_state_when_all_conditions_pass(self, kill_switch, sample_context_data):
        """Test ACTIVE state when all conditions are met."""
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "ACTIVE"
        assert result["usage_policy"]["allowed"] is True
        assert result["usage_policy"]["recommended_weight"] == 1.0
    
    def test_active_state_with_high_confidence(self, kill_switch, sample_context_data):
        """Test ACTIVE state with high confidence."""
        sample_context_data["decision_context"]["confidence"] = 0.90
        sample_context_data["verification"]["stability_score"] = 0.85
        sample_context_data["verification"]["data_completeness"] = 0.95
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "ACTIVE"
        assert result["usage_policy"]["allowed"] is True
    
    # ========================================================================
    # STATE MACHINE TESTS: BLOCKED STATE (Hard Rules)
    # ========================================================================
    
    def test_blocked_when_invariants_failed(self, kill_switch, sample_context_data):
        """Test BLOCKED state when invariants failed."""
        sample_context_data["verification"]["invariants_passed"] = False
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "BLOCKED"
        assert result["usage_policy"]["allowed"] is False
        assert result["decision_context"]["onchain_score"] is None
    
    def test_blocked_when_not_deterministic(self, kill_switch, sample_context_data):
        """Test BLOCKED state when calculation is not deterministic."""
        sample_context_data["verification"]["deterministic"] = False
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "BLOCKED"
        assert result["usage_policy"]["allowed"] is False
    
    def test_blocked_when_data_lag_detected(self, kill_switch, sample_context_data):
        """Test BLOCKED state when data lag is detected."""
        sample_context_data["risk_flags"]["data_lag"] = True
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "BLOCKED"
        assert result["usage_policy"]["allowed"] is False
    
    def test_blocked_when_confidence_below_minimum(self, kill_switch, sample_context_data):
        """Test BLOCKED state when confidence is too low."""
        sample_context_data["decision_context"]["confidence"] = 0.30  # Below min_confidence
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "BLOCKED"
        assert result["usage_policy"]["allowed"] is False
    
    # ========================================================================
    # STATE MACHINE TESTS: DEGRADED STATE
    # ========================================================================
    
    def test_degraded_when_stability_below_threshold(self, kill_switch, sample_context_data):
        """Test DEGRADED state when stability is below threshold."""
        sample_context_data["verification"]["stability_score"] = 0.50  # Below 0.70
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "DEGRADED"
        assert result["usage_policy"]["allowed"] is True
        assert result["usage_policy"]["recommended_weight"] == 0.3
    
    def test_degraded_when_completeness_below_threshold(self, kill_switch, sample_context_data):
        """Test DEGRADED state when data completeness is below threshold."""
        sample_context_data["verification"]["data_completeness"] = 0.70  # Below 0.80
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "DEGRADED"
        assert result["usage_policy"]["allowed"] is True
    
    def test_degraded_when_signal_conflict_detected(self, kill_switch, sample_context_data):
        """Test DEGRADED state when signal conflict is detected."""
        sample_context_data["risk_flags"]["signal_conflict"] = True
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "DEGRADED"
        assert result["usage_policy"]["allowed"] is True
    
    # ========================================================================
    # EDGE CASES
    # ========================================================================
    
    def test_blocked_takes_priority_over_degraded(self, kill_switch, sample_context_data):
        """Test that BLOCKED state takes priority over DEGRADED."""
        # Both blocked and degraded conditions
        sample_context_data["verification"]["invariants_passed"] = False  # BLOCKED
        sample_context_data["verification"]["stability_score"] = 0.50  # DEGRADED
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        # BLOCKED should take priority
        assert result["state"] == "BLOCKED"
        assert result["usage_policy"]["allowed"] is False
    
    def test_multiple_degraded_conditions(self, kill_switch, sample_context_data):
        """Test DEGRADED state with multiple conditions."""
        sample_context_data["verification"]["stability_score"] = 0.50
        sample_context_data["verification"]["data_completeness"] = 0.70
        sample_context_data["risk_flags"]["signal_conflict"] = True
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "DEGRADED"
        assert result["usage_policy"]["allowed"] is True
        assert result["usage_policy"]["recommended_weight"] == 0.3
    
    def test_boundary_confidence_value(self, kill_switch, sample_context_data):
        """Test boundary confidence value (exactly at threshold)."""
        sample_context_data["decision_context"]["confidence"] = 0.60  # Exactly at min_confidence
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        # Should be ACTIVE (>= threshold)
        assert result["state"] == "ACTIVE"
    
    def test_boundary_stability_value(self, kill_switch, sample_context_data):
        """Test boundary stability value."""
        sample_context_data["verification"]["stability_score"] = 0.70  # Exactly at threshold
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        # Should be ACTIVE (>= threshold)
        assert result["state"] == "ACTIVE"
    
    # ========================================================================
    # OUTPUT VALIDATION
    # ========================================================================
    
    def test_output_contains_required_fields(self, kill_switch, sample_context_data):
        """Test that output contains all required fields."""
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        # Required fields
        assert "product" in result
        assert "version" in result
        assert "asset" in result
        assert "timeframe" in result
        assert "timestamp" in result
        assert "state" in result
        assert "decision_context" in result
        assert "signals" in result
        assert "risk_flags" in result
        assert "verification" in result
        assert "usage_policy" in result
    
    def test_usage_policy_structure(self, kill_switch, sample_context_data):
        """Test usage policy structure."""
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        usage_policy = result["usage_policy"]
        assert "allowed" in usage_policy
        assert "recommended_weight" in usage_policy
        assert "notes" in usage_policy
        
        assert isinstance(usage_policy["allowed"], bool)
        assert isinstance(usage_policy["recommended_weight"], (int, float))
        assert 0 <= usage_policy["recommended_weight"] <= 1
    
    def test_score_nullified_when_blocked(self, kill_switch, sample_context_data):
        """Test that onchain_score is set to None when BLOCKED."""
        sample_context_data["verification"]["invariants_passed"] = False
        
        result = kill_switch.evaluate_and_apply(sample_context_data)
        
        assert result["state"] == "BLOCKED"
        assert result["decision_context"]["onchain_score"] is None
        # Bias and confidence should still be present
        assert "bias" in result["decision_context"]
        assert "confidence" in result["decision_context"]


class TestKillSwitchStateTransitions:
    """Test state transitions for kill switch."""
    
    @pytest.fixture
    def config(self):
        config = MagicMock(spec=ProductConfig)
        config.min_confidence = 0.60
        config.stability_threshold = 0.70
        config.completeness_threshold = 0.80
        config.max_data_age_hours = 2.0
        config.max_conflicting_signals = 2
        config.normal_weight = 1.0
        config.degraded_weight = 0.3
        return config
    
    @pytest.fixture
    def kill_switch(self, config):
        return KillSwitchController(config)
    
    def test_transition_active_to_degraded(self, kill_switch, sample_context_data):
        """Test transition from ACTIVE to DEGRADED."""
        # First call - ACTIVE
        result1 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result1["state"] == "ACTIVE"
        
        # Second call with degraded condition
        sample_context_data["verification"]["stability_score"] = 0.50
        result2 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result2["state"] == "DEGRADED"
    
    def test_transition_degraded_to_blocked(self, kill_switch, sample_context_data):
        """Test transition from DEGRADED to BLOCKED."""
        # Degraded condition
        sample_context_data["verification"]["stability_score"] = 0.50
        result1 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result1["state"] == "DEGRADED"
        
        # Add blocked condition
        sample_context_data["verification"]["invariants_passed"] = False
        result2 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result2["state"] == "BLOCKED"
    
    def test_recovery_from_degraded_to_active(self, kill_switch, sample_context_data):
        """Test recovery from DEGRADED to ACTIVE."""
        # Degraded
        sample_context_data["verification"]["stability_score"] = 0.50
        result1 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result1["state"] == "DEGRADED"
        
        # Recovery
        sample_context_data["verification"]["stability_score"] = 0.85
        result2 = kill_switch.evaluate_and_apply(sample_context_data)
        assert result2["state"] == "ACTIVE"
