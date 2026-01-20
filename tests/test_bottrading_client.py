"""
Unit tests for BotTrading Client.

Tests mandatory usage rules and safety checks.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import asyncio


class TestBotTradingClientValidation:
    """Tests for BotTradingClient validation logic."""
    
    @pytest.fixture
    def client(self):
        """Create BotTrading client instance."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        return BotTradingClient(
            api_base_url="http://localhost:8000",
            api_key="test-api-key"
        )
    
    @pytest.fixture
    def valid_context_data(self):
        """Create valid context data."""
        return {
            "state": "ACTIVE",
            "usage_policy": {
                "allowed": True,
                "recommended_weight": 0.3,
                "notes": "Normal operation"
            },
            "decision_context": {
                "onchain_score": 65.0,
                "bias": "positive",
                "confidence": 0.8
            },
            "verification": {
                "invariants_passed": True,
                "deterministic": True,
                "stability_score": 0.95,
                "data_completeness": 0.98
            }
        }
    
    def test_validate_usage_rules_active_state(self, client, valid_context_data):
        """Test validation passes for ACTIVE state with valid data."""
        result = client._validate_usage_rules(valid_context_data)
        assert result is True
    
    def test_validate_usage_rules_blocked_state(self, client, valid_context_data):
        """Test validation fails for BLOCKED state (MANDATORY RULE)."""
        valid_context_data["state"] = "BLOCKED"
        
        result = client._validate_usage_rules(valid_context_data)
        
        # MANDATORY: BLOCKED state MUST reject data
        assert result is False
    
    def test_validate_usage_rules_degraded_state(self, client, valid_context_data):
        """Test validation passes for DEGRADED state with valid policy."""
        valid_context_data["state"] = "DEGRADED"
        
        result = client._validate_usage_rules(valid_context_data)
        assert result is True
    
    def test_validate_usage_rules_not_allowed(self, client, valid_context_data):
        """Test validation fails when usage not allowed."""
        valid_context_data["usage_policy"]["allowed"] = False
        
        result = client._validate_usage_rules(valid_context_data)
        assert result is False
    
    def test_validate_usage_rules_invariants_failed(self, client, valid_context_data):
        """Test validation fails when invariants failed."""
        valid_context_data["verification"]["invariants_passed"] = False
        
        result = client._validate_usage_rules(valid_context_data)
        assert result is False
    
    def test_validate_usage_rules_not_deterministic(self, client, valid_context_data):
        """Test validation fails when not deterministic."""
        valid_context_data["verification"]["deterministic"] = False
        
        result = client._validate_usage_rules(valid_context_data)
        assert result is False
    
    def test_validate_usage_rules_missing_verification(self, client):
        """Test validation fails when verification missing."""
        context_data = {
            "state": "ACTIVE",
            "usage_policy": {
                "allowed": True
            }
            # No verification section
        }
        
        result = client._validate_usage_rules(context_data)
        assert result is False


class TestBotTradingRules:
    """Tests for BotTrading mandatory rules."""
    
    @pytest.fixture
    def client(self):
        """Create BotTrading client instance."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        return BotTradingClient(api_base_url="http://localhost:8000")
    
    def test_apply_trading_rules_positive_bias(self, client):
        """Test trading rules with positive bias."""
        context_data = {
            "decision_context": {
                "bias": "positive",
                "confidence": 0.8
            },
            "usage_policy": {
                "recommended_weight": 0.3
            }
        }
        
        guidance = client.apply_trading_rules(context_data)
        
        # MANDATORY: Must be context only
        assert guidance["use_as_context_only"] is True
        # MANDATORY: Must require confirmation
        assert guidance["requires_confirmation"] is True
        # Positive bias allows long
        assert guidance["allow_long_exposure"] is True
        assert guidance["bias_signal"] == "positive"
    
    def test_apply_trading_rules_negative_bias(self, client):
        """Test trading rules with negative bias (BLOCKS LONG)."""
        context_data = {
            "decision_context": {
                "bias": "negative",
                "confidence": 0.7
            },
            "usage_policy": {
                "recommended_weight": 0.2
            }
        }
        
        guidance = client.apply_trading_rules(context_data)
        
        # MANDATORY: Negative bias MUST block long exposure
        assert guidance["allow_long_exposure"] is False
        # MANDATORY: Must be context only
        assert guidance["use_as_context_only"] is True
        # MANDATORY: Must require confirmation
        assert guidance["requires_confirmation"] is True
        assert guidance["bias_signal"] == "negative"
    
    def test_apply_trading_rules_neutral_bias(self, client):
        """Test trading rules with neutral bias."""
        context_data = {
            "decision_context": {
                "bias": "neutral",
                "confidence": 0.5
            },
            "usage_policy": {
                "recommended_weight": 0.15
            }
        }
        
        guidance = client.apply_trading_rules(context_data)
        
        assert guidance["allow_long_exposure"] is True
        assert guidance["use_as_context_only"] is True
        assert guidance["requires_confirmation"] is True
        assert guidance["bias_signal"] == "neutral"
    
    def test_apply_trading_rules_short_always_allowed(self, client):
        """Test that shorts are always allowed regardless of bias."""
        for bias in ["positive", "neutral", "negative"]:
            context_data = {
                "decision_context": {
                    "bias": bias,
                    "confidence": 0.5
                },
                "usage_policy": {
                    "recommended_weight": 0.2
                }
            }
            
            guidance = client.apply_trading_rules(context_data)
            
            # OnChain doesn't restrict shorts
            assert guidance["allow_short_exposure"] is True
    
    def test_apply_trading_rules_weight_passed_through(self, client):
        """Test that recommended weight is passed through."""
        for weight in [0.0, 0.15, 0.3, 0.5, 1.0]:
            context_data = {
                "decision_context": {
                    "bias": "neutral",
                    "confidence": 0.5
                },
                "usage_policy": {
                    "recommended_weight": weight
                }
            }
            
            guidance = client.apply_trading_rules(context_data)
            assert guidance["context_weight"] == weight


class TestBotTradingClientInitialization:
    """Tests for client initialization."""
    
    def test_client_url_normalization(self):
        """Test URL normalization removes trailing slash."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(api_base_url="http://localhost:8000/")
        assert client.api_base_url == "http://localhost:8000"
        
        client2 = BotTradingClient(api_base_url="http://localhost:8000")
        assert client2.api_base_url == "http://localhost:8000"
    
    def test_client_with_api_key(self):
        """Test client stores API key."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(
            api_base_url="http://localhost:8000",
            api_key="secret-key-123"
        )
        assert client.api_key == "secret-key-123"
    
    def test_client_without_api_key(self):
        """Test client works without API key."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(api_base_url="http://localhost:8000")
        assert client.api_key is None


class TestMandatoryRulesDocumented:
    """Tests to ensure mandatory rules are implemented."""
    
    def test_blocked_state_rejects_usage(self):
        """MANDATORY: BLOCKED state MUST reject data usage."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(api_base_url="http://localhost:8000")
        
        context = {
            "state": "BLOCKED",
            "usage_policy": {"allowed": True},
            "verification": {"invariants_passed": True, "deterministic": True}
        }
        
        # BLOCKED state must return False regardless of other fields
        assert client._validate_usage_rules(context) is False
    
    def test_negative_bias_blocks_long(self):
        """MANDATORY: Negative bias MUST block long exposure."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(api_base_url="http://localhost:8000")
        
        context = {
            "decision_context": {"bias": "negative", "confidence": 0.9},
            "usage_policy": {"recommended_weight": 0.5}
        }
        
        guidance = client.apply_trading_rules(context)
        
        # Even with high confidence, negative bias must block longs
        assert guidance["allow_long_exposure"] is False
    
    def test_always_context_only(self):
        """MANDATORY: OnChain data MUST be context only, never trade trigger."""
        from onchain_intel_product.bottrading_client import BotTradingClient
        
        client = BotTradingClient(api_base_url="http://localhost:8000")
        
        # Test all bias scenarios
        for bias in ["positive", "neutral", "negative"]:
            context = {
                "decision_context": {"bias": bias, "confidence": 1.0},
                "usage_policy": {"recommended_weight": 1.0}
            }
            
            guidance = client.apply_trading_rules(context)
            
            # Must always be context only
            assert guidance["use_as_context_only"] is True
            # Must always require confirmation
            assert guidance["requires_confirmation"] is True
