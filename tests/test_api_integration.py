"""Integration tests for OnChain Intel Product API."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

# Skip API tests if dependencies not properly configured
pytestmark = pytest.mark.skip(reason="API integration tests require compatible httpx/starlette versions")


class TestOnChainContextEndpoint:
    """Test suite for /api/v1/onchain/context endpoint."""
    
    @pytest.fixture
    def mock_service_response(self):
        """Mock response from OnChainIntelligenceService."""
        return {
            "product": "onchain_intelligence",
            "version": "1.0.0",
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": datetime(2024, 1, 15, 12, 0, 0),
            "decision_context": {
                "onchain_score": 72.50,
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
                "stability_score": 0.85,
                "data_completeness": 0.95
            }
        }
    
    def test_context_endpoint_returns_200(self, api_client, mock_intelligence_service, mock_service_response):
        """Test that context endpoint returns 200 OK."""
        mock_service_response["state"] = "ACTIVE"
        mock_service_response["usage_policy"] = {
            "allowed": True,
            "recommended_weight": 1.0,
            "notes": "Data quality verified."
        }
        
        mock_instance = MagicMock()
        mock_instance.get_context_data.return_value = mock_service_response
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?asset=BTC&timeframe=1d")
        
        assert response.status_code == 200
    
    def test_context_endpoint_returns_correct_structure(self, api_client, mock_intelligence_service, mock_service_response):
        """Test that context endpoint returns correct response structure."""
        mock_service_response["state"] = "ACTIVE"
        mock_service_response["usage_policy"] = {
            "allowed": True,
            "recommended_weight": 1.0,
            "notes": "Data quality verified."
        }
        
        mock_instance = MagicMock()
        mock_instance.get_context_data.return_value = mock_service_response
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?asset=BTC&timeframe=1d")
        data = response.json()
        
        assert "product" in data
        assert "state" in data
        assert "decision_context" in data
        assert "signals" in data
        assert "usage_policy" in data
    
    def test_context_endpoint_with_timestamp(self, api_client, mock_intelligence_service, mock_service_response):
        """Test context endpoint with specific timestamp."""
        mock_service_response["state"] = "ACTIVE"
        mock_service_response["usage_policy"] = {
            "allowed": True,
            "recommended_weight": 1.0,
            "notes": "Data quality verified."
        }
        
        mock_instance = MagicMock()
        mock_instance.get_context_data.return_value = mock_service_response
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get(
            "/api/v1/onchain/context?asset=BTC&timeframe=1d&timestamp=2024-01-15T12:00:00Z"
        )
        
        assert response.status_code == 200
    
    def test_context_endpoint_default_asset(self, api_client, mock_intelligence_service, mock_service_response):
        """Test that default asset is BTC."""
        mock_service_response["state"] = "ACTIVE"
        mock_service_response["usage_policy"] = {
            "allowed": True,
            "recommended_weight": 1.0,
            "notes": "Data quality verified."
        }
        
        mock_instance = MagicMock()
        mock_instance.get_context_data.return_value = mock_service_response
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?timeframe=1d")
        data = response.json()
        
        assert data["asset"] == "BTC"
    
    def test_context_endpoint_blocked_state(self, api_client, mock_intelligence_service, mock_service_response):
        """Test context endpoint when state is BLOCKED."""
        mock_service_response["state"] = "BLOCKED"
        mock_service_response["decision_context"]["onchain_score"] = None
        mock_service_response["usage_policy"] = {
            "allowed": False,
            "recommended_weight": 0.0,
            "notes": "BLOCKED: Invariant checks failed."
        }
        
        mock_instance = MagicMock()
        mock_instance.get_context_data.return_value = mock_service_response
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?asset=BTC&timeframe=1d")
        data = response.json()
        
        assert data["state"] == "BLOCKED"
        assert data["usage_policy"]["allowed"] is False
        assert data["decision_context"]["onchain_score"] is None


class TestHealthEndpoint:
    """Test suite for /health endpoint."""
    
    def test_health_returns_200(self, api_client):
        """Test that health endpoint returns 200."""
        response = api_client.get("/health")
        assert response.status_code == 200
    
    def test_health_returns_correct_structure(self, api_client):
        """Test that health endpoint returns correct structure."""
        response = api_client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "product" in data
        assert "version" in data
        assert "timestamp" in data
        assert data["status"] == "healthy"


class TestAuditEndpoint:
    """Test suite for /api/v1/onchain/audit endpoint."""
    
    def test_audit_endpoint_with_valid_timestamp(self, api_client):
        """Test audit endpoint with valid timestamp."""
        with patch('onchain_intel_product.main.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                "input_data_hash": "abc123",
                "calculation_hash": "def456",
                "onchain_score": 72.50,
                "confidence": 0.85,
                "bias": "positive",
                "calculation_time_ms": 156,
                "data_completeness": 0.95
            }
            mock_db.return_value.cursor.return_value = mock_cursor
            
            response = api_client.get(
                "/api/v1/onchain/audit/2024-01-15T12:00:00Z?asset=BTC&timeframe=1d"
            )
            
            # Should return 200 or 404 depending on data availability
            assert response.status_code in [200, 404]
    
    def test_audit_endpoint_invalid_timestamp_format(self, api_client):
        """Test audit endpoint with invalid timestamp format."""
        response = api_client.get(
            "/api/v1/onchain/audit/invalid-timestamp?asset=BTC&timeframe=1d"
        )
        
        assert response.status_code in [400, 422]


class TestAPIErrorHandling:
    """Test API error handling."""
    
    def test_internal_error_returns_500(self, api_client, mock_intelligence_service):
        """Test that internal errors return 500."""
        mock_instance = MagicMock()
        mock_instance.get_context_data.side_effect = Exception("Database error")
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?asset=BTC&timeframe=1d")
        
        assert response.status_code == 500
    
    def test_value_error_returns_400(self, api_client, mock_intelligence_service):
        """Test that value errors return 400."""
        mock_instance = MagicMock()
        mock_instance.get_context_data.side_effect = ValueError("Invalid timeframe")
        mock_intelligence_service.return_value = mock_instance
        
        response = api_client.get("/api/v1/onchain/context?asset=BTC&timeframe=1d")
        
        assert response.status_code == 400
