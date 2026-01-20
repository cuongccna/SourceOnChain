"""Pytest configuration and fixtures for OnChain tests."""

import os
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from unittest.mock import MagicMock, patch


# ============================================================================
# ENVIRONMENT FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture."""
    return {
        "database_url": os.getenv(
            "TEST_DATABASE_URL",
            "postgresql://test_user:test_pass@localhost:5432/test_onchain"
        ),
        "min_confidence": 0.60,
        "stability_threshold": 0.70,
        "completeness_threshold": 0.80,
        "max_data_age_hours": 2.0,
        "max_conflicting_signals": 2,
    }


@pytest.fixture
def sample_timestamp():
    """Sample timestamp for testing."""
    return datetime(2024, 1, 15, 12, 0, 0)


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_onchain_score():
    """Sample OnChain score data."""
    return {
        "timestamp": datetime(2024, 1, 15, 12, 0, 0),
        "asset": "BTC",
        "timeframe": "1d",
        "onchain_score": Decimal("72.50"),
        "confidence": Decimal("0.85"),
        "bias": "positive",
        "network_health_score": Decimal("25.37"),
        "capital_flow_score": Decimal("24.37"),
        "smart_money_score": Decimal("22.76"),
        "risk_penalty": Decimal("0.00"),
        "signal_count": 8,
        "active_signals": 3,
        "conflicting_signals": 0,
        "data_completeness": Decimal("0.95"),
        "calculation_time_ms": 156,
    }


@pytest.fixture
def sample_signals():
    """Sample signals data."""
    return {
        "network_growth_signal": True,
        "network_congestion_signal": False,
        "net_utxo_inflow_signal": True,
        "whale_flow_dominance_signal": False,
        "smart_money_accumulation_signal": True,
        "smart_money_distribution_signal": False,
        "abnormal_activity_signal": False,
        "capital_concentration_signal": False,
    }


@pytest.fixture
def sample_verification():
    """Sample verification data."""
    return {
        "invariants_passed": True,
        "deterministic": True,
        "stability_score": 0.85,
        "data_completeness": 0.95,
    }


@pytest.fixture
def sample_risk_flags():
    """Sample risk flags data."""
    return {
        "data_lag": False,
        "signal_conflict": False,
        "anomaly_detected": False,
    }


@pytest.fixture
def sample_context_data(sample_onchain_score, sample_signals, sample_verification, sample_risk_flags):
    """Complete sample context data."""
    return {
        "product": "onchain_intelligence",
        "version": "1.0.0",
        "asset": "BTC",
        "timeframe": "1d",
        "timestamp": sample_onchain_score["timestamp"],
        "decision_context": {
            "onchain_score": float(sample_onchain_score["onchain_score"]),
            "bias": sample_onchain_score["bias"],
            "confidence": float(sample_onchain_score["confidence"]),
        },
        "signals": sample_signals,
        "risk_flags": sample_risk_flags,
        "verification": sample_verification,
        "raw_data": {
            "score_data": sample_onchain_score,
            "calculation_time": datetime.utcnow(),
        },
    }


# ============================================================================
# WHALE DETECTION FIXTURES
# ============================================================================

@pytest.fixture
def sample_whale_thresholds():
    """Sample whale detection thresholds."""
    return {
        "large_tx_threshold_p95": Decimal("10.5"),
        "whale_tx_threshold_p99": Decimal("100.0"),
        "ultra_whale_threshold_p999": Decimal("1000.0"),
        "leviathan_threshold_p9999": Decimal("5000.0"),
        "sample_size": 50000,
        "threshold_stability_score": Decimal("0.92"),
    }


@pytest.fixture
def sample_whale_activity():
    """Sample whale activity data."""
    return {
        "timestamp": datetime(2024, 1, 15, 12, 0, 0),
        "asset": "BTC",
        "timeframe": "1d",
        "whale_tx_count": 234,
        "whale_tx_volume_btc": Decimal("15678.90"),
        "whale_volume_ratio": Decimal("0.32"),
        "accumulation_flag": True,
        "distribution_flag": False,
        "activity_spike_flag": False,
    }


# ============================================================================
# NETWORK ACTIVITY FIXTURES
# ============================================================================

@pytest.fixture
def sample_network_activity():
    """Sample network activity data."""
    return {
        "timestamp": datetime(2024, 1, 15, 12, 0, 0),
        "asset": "BTC",
        "timeframe": "1d",
        "active_addresses": 850000,
        "tx_count": 320000,
        "total_tx_volume_btc": Decimal("125000.87654321"),
        "avg_tx_value_btc": Decimal("0.39"),
        "blocks_mined": 144,
    }


@pytest.fixture
def sample_utxo_flow():
    """Sample UTXO flow data."""
    return {
        "timestamp": datetime(2024, 1, 15, 12, 0, 0),
        "asset": "BTC",
        "timeframe": "1d",
        "utxo_created_count": 450000,
        "utxo_spent_count": 380000,
        "net_utxo_change": 70000,
        "btc_created": Decimal("85000.0"),
        "btc_spent": Decimal("75000.0"),
        "net_utxo_flow_btc": Decimal("10000.0"),
    }


# ============================================================================
# API TEST FIXTURES
# ============================================================================

@pytest.fixture
def api_client():
    """FastAPI test client."""
    try:
        from fastapi.testclient import TestClient
        import sys
        sys.path.insert(0, 'd:/projects/OnChain/SourceOnChain/onchain_intel_product')
        from main import app
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI app not available")


@pytest.fixture
def mock_intelligence_service():
    """Mock OnChainIntelligenceService."""
    try:
        with patch('main.OnChainIntelligenceService') as mock:
            yield mock
    except Exception:
        yield MagicMock()
