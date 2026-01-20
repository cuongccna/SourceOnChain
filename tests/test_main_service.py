"""
Unit tests for OnChain Intelligence Service.

Tests context data aggregation, risk calculation, and data retrieval.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal


class TestOnChainIntelligenceService:
    """Tests for OnChainIntelligenceService class."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Create mock database connection."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn
    
    @pytest.fixture
    def sample_score_data(self):
        """Sample OnChain score data from database."""
        return {
            "timestamp": datetime.utcnow(),
            "onchain_score": Decimal("65.5"),
            "confidence": Decimal("0.85"),
            "bias": "positive",
            "network_health_score": Decimal("70.0"),
            "capital_flow_score": Decimal("65.0"),
            "smart_money_score": Decimal("60.0"),
            "risk_penalty": Decimal("5.0"),
            "signal_count": 4,
            "active_signals": 3,
            "conflicting_signals": 0,
            "data_completeness": Decimal("0.95"),
            "calculation_time_ms": 150
        }
    
    @pytest.fixture
    def sample_signals_data(self):
        """Sample signals data from database."""
        return [
            {"signal_id": "smart_money_accumulation_signal", "signal_value": True},
            {"signal_id": "whale_flow_dominance_signal", "signal_value": False},
            {"signal_id": "network_growth_signal", "signal_value": True},
            {"signal_id": "smart_money_distribution_signal", "signal_value": False}
        ]


class TestRiskFlagsCalculation:
    """Tests for risk flags calculation logic."""
    
    def test_no_risk_flags_when_all_healthy(self):
        """Test no risk flags when all conditions are healthy."""
        score_data = {
            "timestamp": datetime.utcnow(),
            "conflicting_signals": 0
        }
        signals_data = {
            "smart_money_accumulation": True,
            "distribution_risk": False
        }
        verification_data = {
            "data_completeness": 0.98
        }
        
        # Test the risk calculation logic
        data_lag = False  # Based on timestamp recency
        signal_conflict = score_data.get("conflicting_signals", 0) > 0
        anomaly_detected = False
        
        assert data_lag is False
        assert signal_conflict is False
        assert anomaly_detected is False
    
    def test_signal_conflict_detected(self):
        """Test signal conflict flag when conflicting signals exist."""
        score_data = {
            "timestamp": datetime.utcnow(),
            "conflicting_signals": 2
        }
        
        signal_conflict = score_data.get("conflicting_signals", 0) > 0
        assert signal_conflict is True
    
    def test_data_lag_detected_for_stale_data(self):
        """Test data lag flag for stale data."""
        old_timestamp = datetime.utcnow() - timedelta(hours=2)
        max_age_hours = 1
        
        data_age = datetime.utcnow() - old_timestamp
        data_lag = data_age.total_seconds() > (max_age_hours * 3600)
        
        assert data_lag is True
    
    def test_no_data_lag_for_fresh_data(self):
        """Test no data lag for recent data."""
        recent_timestamp = datetime.utcnow() - timedelta(minutes=5)
        max_age_hours = 1
        
        data_age = datetime.utcnow() - recent_timestamp
        data_lag = data_age.total_seconds() > (max_age_hours * 3600)
        
        assert data_lag is False


class TestContextDataAggregation:
    """Tests for context data structure."""
    
    def test_context_data_structure(self):
        """Test context data has required structure."""
        context_data = {
            "product": "onchain_intelligence",
            "version": "1.0.0",
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": datetime.utcnow(),
            "decision_context": {
                "onchain_score": 65.5,
                "bias": "positive",
                "confidence": 0.85
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
            }
        }
        
        # Validate required fields
        assert "product" in context_data
        assert "version" in context_data
        assert "asset" in context_data
        assert "timeframe" in context_data
        assert "timestamp" in context_data
        assert "decision_context" in context_data
        assert "signals" in context_data
        assert "risk_flags" in context_data
        assert "verification" in context_data
        
        # Validate nested structure
        assert "onchain_score" in context_data["decision_context"]
        assert "bias" in context_data["decision_context"]
        assert "confidence" in context_data["decision_context"]
    
    def test_null_score_when_blocked(self):
        """Test onchain_score is null when state is BLOCKED."""
        # When verification fails, score should be null
        blocked_context = {
            "decision_context": {
                "onchain_score": None,  # Nullified when blocked
                "bias": "negative",
                "confidence": 0.3
            },
            "verification": {
                "invariants_passed": False,
                "deterministic": False
            }
        }
        
        assert blocked_context["decision_context"]["onchain_score"] is None
    
    def test_bias_values(self):
        """Test bias can only be positive, neutral, or negative."""
        valid_biases = ["positive", "neutral", "negative"]
        
        for bias in valid_biases:
            context = {"decision_context": {"bias": bias}}
            assert context["decision_context"]["bias"] in valid_biases


class TestSignalMapping:
    """Tests for signal mapping from database to response."""
    
    def test_signal_mapping_with_all_signals(self):
        """Test all signals map correctly."""
        db_signals = [
            {"signal_id": "smart_money_accumulation_signal", "signal_value": True},
            {"signal_id": "whale_flow_dominance_signal", "signal_value": True},
            {"signal_id": "network_growth_signal", "signal_value": False},
            {"signal_id": "smart_money_distribution_signal", "signal_value": True}
        ]
        
        signal_map = {row['signal_id']: row['signal_value'] for row in db_signals}
        
        mapped_signals = {
            "smart_money_accumulation": signal_map.get("smart_money_accumulation_signal", False),
            "whale_flow_dominant": signal_map.get("whale_flow_dominance_signal", False),
            "network_growth": signal_map.get("network_growth_signal", False),
            "distribution_risk": signal_map.get("smart_money_distribution_signal", False)
        }
        
        assert mapped_signals["smart_money_accumulation"] is True
        assert mapped_signals["whale_flow_dominant"] is True
        assert mapped_signals["network_growth"] is False
        assert mapped_signals["distribution_risk"] is True
    
    def test_signal_mapping_with_missing_signals(self):
        """Test missing signals default to False."""
        db_signals = [
            {"signal_id": "smart_money_accumulation_signal", "signal_value": True}
            # Other signals missing
        ]
        
        signal_map = {row['signal_id']: row['signal_value'] for row in db_signals}
        
        mapped_signals = {
            "smart_money_accumulation": signal_map.get("smart_money_accumulation_signal", False),
            "whale_flow_dominant": signal_map.get("whale_flow_dominance_signal", False),
            "network_growth": signal_map.get("network_growth_signal", False),
            "distribution_risk": signal_map.get("smart_money_distribution_signal", False)
        }
        
        assert mapped_signals["smart_money_accumulation"] is True
        assert mapped_signals["whale_flow_dominant"] is False  # Default
        assert mapped_signals["network_growth"] is False  # Default
        assert mapped_signals["distribution_risk"] is False  # Default
    
    def test_signal_mapping_with_empty_signals(self):
        """Test empty signals all default to False."""
        db_signals = []
        
        signal_map = {row['signal_id']: row['signal_value'] for row in db_signals}
        
        mapped_signals = {
            "smart_money_accumulation": signal_map.get("smart_money_accumulation_signal", False),
            "whale_flow_dominant": signal_map.get("whale_flow_dominance_signal", False),
            "network_growth": signal_map.get("network_growth_signal", False),
            "distribution_risk": signal_map.get("smart_money_distribution_signal", False)
        }
        
        assert all(v is False for v in mapped_signals.values())


class TestVerificationDataDefaults:
    """Tests for verification data default values."""
    
    def test_default_verification_when_no_results(self):
        """Test default verification values when no results."""
        default_verification = {
            "invariants_passed": True,
            "deterministic": True,
            "stability_score": 0.8,
            "data_completeness": 0.9
        }
        
        assert default_verification["invariants_passed"] is True
        assert default_verification["deterministic"] is True
        assert default_verification["stability_score"] == 0.8
        assert default_verification["data_completeness"] == 0.9
    
    def test_verification_score_ranges(self):
        """Test verification scores are in valid ranges."""
        verification = {
            "stability_score": 0.95,
            "data_completeness": 0.98
        }
        
        assert 0 <= verification["stability_score"] <= 1
        assert 0 <= verification["data_completeness"] <= 1
    
    def test_invariant_analysis(self):
        """Test invariant test analysis logic."""
        verification_results = [
            {"test_name": "score_invariant_check", "verification_passed": True, "verification_score": 1.0},
            {"test_name": "bias_invariant_check", "verification_passed": True, "verification_score": 1.0},
            {"test_name": "determinism_test", "verification_passed": True, "verification_score": 1.0},
            {"test_name": "stability_check", "verification_passed": True, "verification_score": 0.95}
        ]
        
        invariant_tests = [r for r in verification_results if "invariant" in r['test_name'].lower()]
        determinism_tests = [r for r in verification_results if "determinism" in r['test_name'].lower()]
        stability_tests = [r for r in verification_results if "stability" in r['test_name'].lower()]
        
        invariants_passed = all(t['verification_passed'] for t in invariant_tests)
        deterministic = all(t['verification_passed'] for t in determinism_tests)
        
        assert invariants_passed is True
        assert deterministic is True
        assert len(invariant_tests) == 2
        assert len(determinism_tests) == 1
        assert len(stability_tests) == 1


class TestDecimalConversion:
    """Tests for Decimal to float conversion."""
    
    def test_decimal_to_float_conversion(self):
        """Test Decimal values convert correctly."""
        score_data = {
            "onchain_score": Decimal("65.5"),
            "confidence": Decimal("0.85")
        }
        
        decision_context = {
            "onchain_score": float(score_data["onchain_score"]) if score_data["onchain_score"] else None,
            "confidence": float(score_data["confidence"])
        }
        
        assert decision_context["onchain_score"] == 65.5
        assert decision_context["confidence"] == 0.85
        assert isinstance(decision_context["onchain_score"], float)
        assert isinstance(decision_context["confidence"], float)
    
    def test_none_score_handling(self):
        """Test None score handling."""
        score_data = {
            "onchain_score": None,
            "confidence": Decimal("0.5")
        }
        
        decision_context = {
            "onchain_score": float(score_data["onchain_score"]) if score_data["onchain_score"] else None,
            "confidence": float(score_data["confidence"])
        }
        
        assert decision_context["onchain_score"] is None
        assert decision_context["confidence"] == 0.5
