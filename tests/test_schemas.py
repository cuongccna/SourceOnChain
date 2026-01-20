"""
Unit tests for Pydantic schemas.

Tests schema validation, constraints, and serialization.
"""

import pytest
from datetime import datetime
from decimal import Decimal


class TestDecisionContextSchema:
    """Tests for DecisionContext schema."""
    
    def test_valid_decision_context(self):
        """Test valid decision context creation."""
        from onchain_intel_product.schemas import DecisionContext
        
        context = DecisionContext(
            onchain_score=65.5,
            bias="positive",
            confidence=0.8
        )
        
        assert context.onchain_score == 65.5
        assert context.bias == "positive"
        assert context.confidence == 0.8
    
    def test_onchain_score_can_be_null(self):
        """Test onchain_score can be null (for blocked state)."""
        from onchain_intel_product.schemas import DecisionContext
        
        context = DecisionContext(
            onchain_score=None,
            bias="negative",
            confidence=0.5
        )
        
        assert context.onchain_score is None
    
    def test_onchain_score_range_validation(self):
        """Test onchain_score must be 0-100."""
        from onchain_intel_product.schemas import DecisionContext
        from pydantic import ValidationError
        
        # Valid scores
        for score in [0, 50, 100, 0.0, 100.0]:
            context = DecisionContext(
                onchain_score=score,
                bias="neutral",
                confidence=0.5
            )
            assert 0 <= context.onchain_score <= 100
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            DecisionContext(onchain_score=-1, bias="neutral", confidence=0.5)
        
        # Invalid: over 100
        with pytest.raises(ValidationError):
            DecisionContext(onchain_score=101, bias="neutral", confidence=0.5)
    
    def test_confidence_range_validation(self):
        """Test confidence must be 0-1."""
        from onchain_intel_product.schemas import DecisionContext
        from pydantic import ValidationError
        
        # Valid confidence
        for conf in [0.0, 0.5, 1.0]:
            context = DecisionContext(
                onchain_score=50,
                bias="neutral",
                confidence=conf
            )
            assert 0 <= context.confidence <= 1
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            DecisionContext(onchain_score=50, bias="neutral", confidence=-0.1)
        
        # Invalid: over 1
        with pytest.raises(ValidationError):
            DecisionContext(onchain_score=50, bias="neutral", confidence=1.1)
    
    def test_bias_literal_validation(self):
        """Test bias must be one of allowed values."""
        from onchain_intel_product.schemas import DecisionContext
        from pydantic import ValidationError
        
        # Valid biases
        for bias in ["positive", "neutral", "negative"]:
            context = DecisionContext(
                onchain_score=50,
                bias=bias,
                confidence=0.5
            )
            assert context.bias == bias
        
        # Invalid bias
        with pytest.raises(ValidationError):
            DecisionContext(onchain_score=50, bias="bullish", confidence=0.5)


class TestSignalsSchema:
    """Tests for Signals schema."""
    
    def test_valid_signals(self):
        """Test valid signals creation."""
        from onchain_intel_product.schemas import Signals
        
        signals = Signals(
            smart_money_accumulation=True,
            whale_flow_dominant=False,
            network_growth=True,
            distribution_risk=False
        )
        
        assert signals.smart_money_accumulation is True
        assert signals.whale_flow_dominant is False
        assert signals.network_growth is True
        assert signals.distribution_risk is False
    
    def test_all_signals_required(self):
        """Test all signal fields are required."""
        from onchain_intel_product.schemas import Signals
        from pydantic import ValidationError
        
        # Missing fields should raise error
        with pytest.raises(ValidationError):
            Signals(smart_money_accumulation=True)
    
    def test_signals_all_true(self):
        """Test all signals can be true."""
        from onchain_intel_product.schemas import Signals
        
        signals = Signals(
            smart_money_accumulation=True,
            whale_flow_dominant=True,
            network_growth=True,
            distribution_risk=True
        )
        
        assert all([
            signals.smart_money_accumulation,
            signals.whale_flow_dominant,
            signals.network_growth,
            signals.distribution_risk
        ])
    
    def test_signals_all_false(self):
        """Test all signals can be false."""
        from onchain_intel_product.schemas import Signals
        
        signals = Signals(
            smart_money_accumulation=False,
            whale_flow_dominant=False,
            network_growth=False,
            distribution_risk=False
        )
        
        assert not any([
            signals.smart_money_accumulation,
            signals.whale_flow_dominant,
            signals.network_growth,
            signals.distribution_risk
        ])


class TestRiskFlagsSchema:
    """Tests for RiskFlags schema."""
    
    def test_valid_risk_flags(self):
        """Test valid risk flags creation."""
        from onchain_intel_product.schemas import RiskFlags
        
        flags = RiskFlags(
            data_lag=False,
            signal_conflict=False,
            anomaly_detected=False
        )
        
        assert flags.data_lag is False
        assert flags.signal_conflict is False
        assert flags.anomaly_detected is False
    
    def test_all_flags_set(self):
        """Test all risk flags can be set."""
        from onchain_intel_product.schemas import RiskFlags
        
        flags = RiskFlags(
            data_lag=True,
            signal_conflict=True,
            anomaly_detected=True
        )
        
        assert flags.data_lag is True
        assert flags.signal_conflict is True
        assert flags.anomaly_detected is True


class TestVerificationSchema:
    """Tests for Verification schema."""
    
    def test_valid_verification(self):
        """Test valid verification creation."""
        from onchain_intel_product.schemas import Verification
        
        verification = Verification(
            invariants_passed=True,
            deterministic=True,
            stability_score=0.95,
            data_completeness=0.98
        )
        
        assert verification.invariants_passed is True
        assert verification.deterministic is True
        assert verification.stability_score == 0.95
        assert verification.data_completeness == 0.98
    
    def test_stability_score_range(self):
        """Test stability_score must be 0-1."""
        from onchain_intel_product.schemas import Verification
        from pydantic import ValidationError
        
        # Valid
        v = Verification(
            invariants_passed=True,
            deterministic=True,
            stability_score=0.5,
            data_completeness=0.5
        )
        assert v.stability_score == 0.5
        
        # Invalid
        with pytest.raises(ValidationError):
            Verification(
                invariants_passed=True,
                deterministic=True,
                stability_score=1.5,
                data_completeness=0.5
            )
    
    def test_data_completeness_range(self):
        """Test data_completeness must be 0-1."""
        from onchain_intel_product.schemas import Verification
        from pydantic import ValidationError
        
        # Invalid: over 1
        with pytest.raises(ValidationError):
            Verification(
                invariants_passed=True,
                deterministic=True,
                stability_score=0.5,
                data_completeness=1.1
            )


class TestUsagePolicySchema:
    """Tests for UsagePolicy schema."""
    
    def test_valid_usage_policy(self):
        """Test valid usage policy creation."""
        from onchain_intel_product.schemas import UsagePolicy
        
        policy = UsagePolicy(
            allowed=True,
            recommended_weight=0.3,
            notes="Normal operation"
        )
        
        assert policy.allowed is True
        assert policy.recommended_weight == 0.3
        assert policy.notes == "Normal operation"
    
    def test_recommended_weight_range(self):
        """Test recommended_weight must be 0-1."""
        from onchain_intel_product.schemas import UsagePolicy
        from pydantic import ValidationError
        
        # Valid weights
        for weight in [0.0, 0.15, 0.3, 0.5, 1.0]:
            policy = UsagePolicy(
                allowed=True,
                recommended_weight=weight,
                notes="test"
            )
            assert policy.recommended_weight == weight
        
        # Invalid
        with pytest.raises(ValidationError):
            UsagePolicy(allowed=True, recommended_weight=1.5, notes="test")


class TestOnChainContextResponseSchema:
    """Tests for complete OnChainContextResponse schema."""
    
    @pytest.fixture
    def valid_response_data(self):
        """Create valid response data."""
        return {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": datetime.utcnow(),
            "state": "ACTIVE",
            "decision_context": {
                "onchain_score": 65.0,
                "bias": "positive",
                "confidence": 0.8
            },
            "signals": {
                "smart_money_accumulation": True,
                "whale_flow_dominant": False,
                "network_growth": True,
                "distribution_risk": False
            },
            "risk_flags": {
                "data_lag": False,
                "signal_conflict": False,
                "anomaly_detected": False
            },
            "verification": {
                "invariants_passed": True,
                "deterministic": True,
                "stability_score": 0.95,
                "data_completeness": 0.98
            },
            "usage_policy": {
                "allowed": True,
                "recommended_weight": 0.3,
                "notes": "Normal operation"
            }
        }
    
    def test_valid_response(self, valid_response_data):
        """Test valid response creation."""
        from onchain_intel_product.schemas import OnChainContextResponse
        
        response = OnChainContextResponse(**valid_response_data)
        
        assert response.product == "onchain_intelligence"
        assert response.version == "1.0.0"
        assert response.asset == "BTC"
        assert response.state == "ACTIVE"
    
    def test_state_must_be_valid(self, valid_response_data):
        """Test state must be ACTIVE, DEGRADED, or BLOCKED."""
        from onchain_intel_product.schemas import OnChainContextResponse
        from pydantic import ValidationError
        
        # Valid states
        for state in ["ACTIVE", "DEGRADED", "BLOCKED"]:
            valid_response_data["state"] = state
            response = OnChainContextResponse(**valid_response_data)
            assert response.state == state
        
        # Invalid state
        valid_response_data["state"] = "INVALID"
        with pytest.raises(ValidationError):
            OnChainContextResponse(**valid_response_data)
    
    def test_response_serialization(self, valid_response_data):
        """Test response serializes to JSON correctly."""
        from onchain_intel_product.schemas import OnChainContextResponse
        
        response = OnChainContextResponse(**valid_response_data)
        json_data = response.model_dump()
        
        assert "product" in json_data
        assert "version" in json_data
        assert "state" in json_data
        assert "decision_context" in json_data
        assert "signals" in json_data
        assert "risk_flags" in json_data
        assert "verification" in json_data
        assert "usage_policy" in json_data


class TestAuditResponseSchema:
    """Tests for AuditResponse schema."""
    
    def test_valid_audit_response(self):
        """Test valid audit response creation."""
        from onchain_intel_product.schemas import AuditResponse
        
        audit = AuditResponse(
            timestamp=datetime.utcnow(),
            asset="BTC",
            timeframe="1d",
            input_data_hash="abc123def456",
            config_hash="xyz789",
            output_snapshot={"score": 65.0, "bias": "positive"}
        )
        
        assert audit.asset == "BTC"
        assert audit.input_data_hash == "abc123def456"
        assert audit.output_snapshot["score"] == 65.0
    
    def test_output_snapshot_flexible(self):
        """Test output_snapshot accepts any dict structure."""
        from onchain_intel_product.schemas import AuditResponse
        
        audit = AuditResponse(
            timestamp=datetime.utcnow(),
            asset="BTC",
            timeframe="1d",
            input_data_hash="hash1",
            config_hash="hash2",
            output_snapshot={
                "nested": {"deep": {"value": 123}},
                "list": [1, 2, 3],
                "mixed": {"items": [{"a": 1}, {"b": 2}]}
            }
        )
        
        assert audit.output_snapshot["nested"]["deep"]["value"] == 123
        assert audit.output_snapshot["list"] == [1, 2, 3]
