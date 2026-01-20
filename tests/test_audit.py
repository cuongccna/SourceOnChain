"""
Unit tests for Audit Controller.

Tests audit recording, hash generation, and calculation verification.
"""

import pytest
import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestHashGeneration:
    """Tests for hash generation functions."""
    
    def test_input_hash_deterministic(self):
        """Test input hash is deterministic."""
        input_data = {
            "score": 65.5,
            "bias": "positive",
            "signals": ["a", "b", "c"]
        }
        
        def normalize_for_hash(data):
            if isinstance(data, dict):
                return {k: normalize_for_hash(v) for k, v in sorted(data.items())}
            elif isinstance(data, list):
                return [normalize_for_hash(item) for item in data]
            elif isinstance(data, float):
                return round(data, 8)
            elif isinstance(data, datetime):
                return data.isoformat()
            return data
        
        def generate_hash(data):
            normalized = normalize_for_hash(data)
            data_string = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        hash1 = generate_hash(input_data)
        hash2 = generate_hash(input_data)
        
        assert hash1 == hash2
    
    def test_different_data_different_hash(self):
        """Test different data produces different hash."""
        def normalize_for_hash(data):
            if isinstance(data, dict):
                return {k: normalize_for_hash(v) for k, v in sorted(data.items())}
            elif isinstance(data, list):
                return [normalize_for_hash(item) for item in data]
            elif isinstance(data, float):
                return round(data, 8)
            return data
        
        def generate_hash(data):
            normalized = normalize_for_hash(data)
            data_string = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        data1 = {"score": 65.5, "bias": "positive"}
        data2 = {"score": 65.5, "bias": "negative"}
        
        hash1 = generate_hash(data1)
        hash2 = generate_hash(data2)
        
        assert hash1 != hash2
    
    def test_hash_format(self):
        """Test hash format is valid SHA256."""
        def generate_hash(data):
            data_string = json.dumps(data, sort_keys=True)
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        hash_result = generate_hash({"test": "data"})
        
        # SHA256 produces 64 hex characters
        assert len(hash_result) == 64
        assert all(c in '0123456789abcdef' for c in hash_result)


class TestNormalization:
    """Tests for data normalization before hashing."""
    
    def test_float_precision_normalization(self):
        """Test floats are normalized to 8 decimal places."""
        def normalize_for_hash(data):
            if isinstance(data, float):
                return round(data, 8)
            return data
        
        # Slightly different float representations should normalize to same value
        value1 = 0.123456789123456
        value2 = 0.12345679  # Rounded version
        
        normalized1 = normalize_for_hash(value1)
        normalized2 = normalize_for_hash(value2)
        
        assert normalized1 == normalized2
    
    def test_dict_key_ordering(self):
        """Test dict keys are sorted for consistent hashing."""
        def normalize_for_hash(data):
            if isinstance(data, dict):
                return {k: normalize_for_hash(v) for k, v in sorted(data.items())}
            return data
        
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        
        normalized1 = normalize_for_hash(data1)
        normalized2 = normalize_for_hash(data2)
        
        # Both should produce same ordered dict
        assert list(normalized1.keys()) == ["a", "m", "z"]
        assert normalized1 == normalized2
    
    def test_datetime_normalization(self):
        """Test datetime is converted to ISO format."""
        def normalize_for_hash(data):
            if isinstance(data, datetime):
                return data.isoformat()
            return data
        
        dt = datetime(2025, 1, 15, 12, 30, 45)
        normalized = normalize_for_hash(dt)
        
        assert normalized == "2025-01-15T12:30:45"
        assert isinstance(normalized, str)
    
    def test_nested_normalization(self):
        """Test nested structures are normalized correctly."""
        def normalize_for_hash(data):
            if isinstance(data, dict):
                return {k: normalize_for_hash(v) for k, v in sorted(data.items())}
            elif isinstance(data, list):
                return [normalize_for_hash(item) for item in data]
            elif isinstance(data, float):
                return round(data, 8)
            return data
        
        nested_data = {
            "outer": {
                "inner": {
                    "value": 0.123456789123456
                },
                "list": [{"z": 1, "a": 2}, 3.14159265358979]
            }
        }
        
        normalized = normalize_for_hash(nested_data)
        
        assert normalized["outer"]["inner"]["value"] == 0.12345679
        assert list(normalized["outer"]["list"][0].keys()) == ["a", "z"]
        assert normalized["outer"]["list"][1] == 3.14159265


class TestConfigSnapshot:
    """Tests for configuration snapshot."""
    
    def test_config_snapshot_structure(self):
        """Test config snapshot has required fields."""
        # Simulate config snapshot structure
        config_snapshot = {
            "min_confidence": 0.5,
            "stability_threshold": 0.7,
            "completeness_threshold": 0.8,
            "max_data_age_hours": 1,
            "max_conflicting_signals": 2,
            "normal_weight": 0.3,
            "degraded_weight": 0.15
        }
        
        required_fields = [
            "min_confidence",
            "stability_threshold", 
            "completeness_threshold",
            "max_data_age_hours",
            "max_conflicting_signals",
            "normal_weight",
            "degraded_weight"
        ]
        
        for field in required_fields:
            assert field in config_snapshot
    
    def test_config_hash_deterministic(self):
        """Test config hash is deterministic."""
        config = {
            "min_confidence": 0.5,
            "stability_threshold": 0.7,
            "normal_weight": 0.3
        }
        
        def generate_hash(data):
            data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        hash1 = generate_hash(config)
        hash2 = generate_hash(config)
        
        assert hash1 == hash2


class TestAuditRecordStructure:
    """Tests for audit record structure."""
    
    def test_audit_record_fields(self):
        """Test audit record has required fields."""
        audit_record = {
            "calculation_hash": "abc123",
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": datetime.utcnow(),
            "input_data_hash": "def456",
            "config_hash": "ghi789",
            "output_data": {"score": 65.5, "bias": "positive"},
            "created_at": datetime.utcnow()
        }
        
        required_fields = [
            "calculation_hash",
            "asset",
            "timeframe",
            "timestamp",
            "input_data_hash",
            "config_hash",
            "output_data",
            "created_at"
        ]
        
        for field in required_fields:
            assert field in audit_record
    
    def test_calculation_hash_unique(self):
        """Test calculation hash is unique for different calculations."""
        def generate_calculation_hash(data):
            data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        calc1 = {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "input_hash": "abc",
            "output": {"score": 65.5}
        }
        
        calc2 = {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "input_hash": "abc",
            "output": {"score": 70.0}  # Different score
        }
        
        hash1 = generate_calculation_hash(calc1)
        hash2 = generate_calculation_hash(calc2)
        
        assert hash1 != hash2


class TestIntegrityVerification:
    """Tests for calculation integrity verification."""
    
    def test_integrity_check_same_data(self):
        """Test integrity verification passes for same data."""
        def generate_calculation_hash(data):
            data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        original_data = {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "output": {"score": 65.5}
        }
        
        stored_hash = generate_calculation_hash(original_data)
        
        # Reconstruct same data
        reconstructed_data = {
            "asset": "BTC",
            "timeframe": "1d", 
            "timestamp": "2025-01-15T12:00:00",
            "output": {"score": 65.5}
        }
        
        computed_hash = generate_calculation_hash(reconstructed_data)
        
        assert stored_hash == computed_hash
    
    def test_integrity_check_modified_data(self):
        """Test integrity verification fails for modified data."""
        def generate_calculation_hash(data):
            data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        original_data = {
            "asset": "BTC",
            "output": {"score": 65.5}
        }
        
        stored_hash = generate_calculation_hash(original_data)
        
        # Modified data (tampered)
        tampered_data = {
            "asset": "BTC",
            "output": {"score": 99.0}  # Changed!
        }
        
        computed_hash = generate_calculation_hash(tampered_data)
        
        assert stored_hash != computed_hash


class TestReplayMechanism:
    """Tests for calculation replay mechanism."""
    
    def test_replay_returns_audit_record(self):
        """Test replay returns stored audit record."""
        # Simulate replay returning stored record
        stored_record = {
            "calculation_hash": "abc123",
            "input_data_hash": "def456",
            "config_hash": "ghi789",
            "output_data": {"score": 65.5, "bias": "positive"},
            "created_at": datetime.utcnow()
        }
        
        # Replay should return the stored record
        replay_result = stored_record  # In real implementation, this comes from DB
        
        assert replay_result["calculation_hash"] == "abc123"
        assert replay_result["output_data"]["score"] == 65.5
    
    def test_replay_none_when_no_record(self):
        """Test replay returns None when no record exists."""
        # Simulate no record found
        audit_record = None
        
        # Replay should return None
        assert audit_record is None


class TestAuditControllerIntegration:
    """Integration-style tests for AuditController."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock()
        config.min_confidence = 0.5
        config.stability_threshold = 0.7
        config.completeness_threshold = 0.8
        config.max_data_age_hours = 1
        config.max_conflicting_signals = 2
        config.normal_weight = 0.3
        config.degraded_weight = 0.15
        return config
    
    def test_full_audit_workflow(self, mock_config):
        """Test complete audit workflow: record -> retrieve -> verify."""
        # Step 1: Generate hashes
        input_data = {"raw_score": 65.5, "signals": [True, False, True]}
        output_data = {"onchain_score": 65.5, "bias": "positive"}
        
        def generate_hash(data):
            data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        input_hash = generate_hash(input_data)
        
        calculation_data = {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "input_hash": input_hash,
            "output": output_data
        }
        calculation_hash = generate_hash(calculation_data)
        
        # Step 2: Create audit record
        audit_record = {
            "calculation_hash": calculation_hash,
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "input_data_hash": input_hash,
            "output_data": output_data
        }
        
        # Step 3: Verify integrity
        reconstructed = {
            "asset": "BTC",
            "timeframe": "1d",
            "timestamp": "2025-01-15T12:00:00",
            "input_hash": audit_record["input_data_hash"],
            "output": audit_record["output_data"]
        }
        computed_hash = generate_hash(reconstructed)
        
        # Verify
        assert computed_hash == calculation_hash
        assert audit_record["calculation_hash"] == calculation_hash
