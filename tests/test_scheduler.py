"""
Unit tests for OnChain Pipeline Scheduler.

Tests scheduler configuration, pipeline logic, and state management.
"""

import pytest
import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Pre-import the module to ensure it's available for patching
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSchedulerConfig:
    """Tests for SchedulerConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        # Import after setting up path
        import importlib
        import onchain_intel_product.scheduler as scheduler_module
        importlib.reload(scheduler_module)
        
        SchedulerConfig = scheduler_module.SchedulerConfig
        
        # Create config with defaults (env vars may be set)
        config = SchedulerConfig()
        
        # Test that config has expected attributes
        assert hasattr(config, 'interval_minutes')
        assert hasattr(config, 'log_level')
        assert hasattr(config, 'enable_collection')
        assert hasattr(config, 'enable_normalization')
        assert hasattr(config, 'enable_whale_detection')
        assert hasattr(config, 'enable_smart_wallet')
        assert hasattr(config, 'enable_signal_engine')
        assert hasattr(config, 'timeframes')
        
        # Verify types
        assert isinstance(config.interval_minutes, int)
        assert isinstance(config.enable_collection, bool)
    
    def test_custom_config_from_env(self):
        """Test configuration from environment variables."""
        import importlib
        import onchain_intel_product.scheduler as scheduler_module
        
        env_vars = {
            "ONCHAIN_DATABASE_URL": "postgresql://test:test@localhost/test",
            "ONCHAIN_SCHEDULER_INTERVAL": "10",
            "ONCHAIN_LOG_LEVEL": "DEBUG",
            "ONCHAIN_ENABLE_COLLECTION": "false",
            "ONCHAIN_ENABLE_NORMALIZATION": "false",
            "ONCHAIN_ENABLE_WHALE_DETECTION": "true",
            "ONCHAIN_ENABLE_SMART_WALLET": "false",
            "ONCHAIN_ENABLE_SIGNAL_ENGINE": "true",
            "ONCHAIN_TIMEFRAMES": "1h,4h,1d,1w"
        }
        
        with patch.dict(os.environ, env_vars):
            importlib.reload(scheduler_module)
            SchedulerConfig = scheduler_module.SchedulerConfig
            config = SchedulerConfig()
            
            assert config.database_url == "postgresql://test:test@localhost/test"
            assert config.interval_minutes == 10
            assert config.log_level == "DEBUG"
            assert config.enable_collection is False
            assert config.enable_normalization is False
            assert config.enable_whale_detection is True
            assert config.enable_smart_wallet is False
            assert config.enable_signal_engine is True
            assert config.timeframes == ["1h", "4h", "1d", "1w"]
    
    def test_boolean_parsing_case_insensitive(self):
        """Test boolean parsing is case insensitive."""
        import importlib
        import onchain_intel_product.scheduler as scheduler_module
        
        env_vars = {
            "ONCHAIN_ENABLE_COLLECTION": "TRUE",
            "ONCHAIN_ENABLE_NORMALIZATION": "True",
            "ONCHAIN_ENABLE_WHALE_DETECTION": "FALSE",
            "ONCHAIN_ENABLE_SMART_WALLET": "False",
        }
        
        with patch.dict(os.environ, env_vars):
            importlib.reload(scheduler_module)
            SchedulerConfig = scheduler_module.SchedulerConfig
            config = SchedulerConfig()
            
            assert config.enable_collection is True
            assert config.enable_normalization is True
            assert config.enable_whale_detection is False
            assert config.enable_smart_wallet is False


class TestOnChainPipelineScheduler:
    """Tests for OnChainPipelineScheduler class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock scheduler config."""
        config = Mock()
        config.database_url = "postgresql://test:test@localhost/test"
        config.interval_minutes = 5
        config.timeframes = ["1h", "4h", "1d"]
        config.enable_collection = True
        config.enable_normalization = True
        config.enable_whale_detection = True
        config.enable_smart_wallet = True
        config.enable_signal_engine = True
        return config
    
    def test_scheduler_initialization(self, mock_config):
        """Test scheduler initializes correctly."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine') as mock_create_engine, \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=mock_config)
            
            assert scheduler.config == mock_config
            assert scheduler.running is True
            mock_create_engine.assert_called_once_with(mock_config.database_url)
    
    def test_shutdown_handler(self, mock_config):
        """Test shutdown handler sets running to False."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=mock_config)
            assert scheduler.running is True
            
            # Simulate shutdown signal
            scheduler._shutdown_handler(2, None)  # SIGINT
            
            assert scheduler.running is False
    
    def test_pipeline_with_all_stages_disabled(self, mock_config):
        """Test pipeline runs with all stages disabled."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            # Disable all stages
            mock_config.enable_collection = False
            mock_config.enable_normalization = False
            mock_config.enable_whale_detection = False
            mock_config.enable_smart_wallet = False
            mock_config.enable_signal_engine = False
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=mock_config)
            
            # Mock the update state method
            scheduler._update_scheduler_state = Mock()
            
            # Run pipeline - should complete without errors
            scheduler.run_pipeline()
            
            # Verify state was updated
            scheduler._update_scheduler_state.assert_called_once()
            call_args = scheduler._update_scheduler_state.call_args
            assert call_args[0][0] == "success"
    
    def test_pipeline_handles_exception(self, mock_config):
        """Test pipeline handles exceptions gracefully."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=mock_config)
            
            # Mock collection to raise exception
            scheduler._run_collection = Mock(side_effect=Exception("Test error"))
            scheduler._update_scheduler_state = Mock()
            
            # Run pipeline - should catch exception
            scheduler.run_pipeline()
            
            # Verify error state was recorded
            scheduler._update_scheduler_state.assert_called_once()
            call_args = scheduler._update_scheduler_state.call_args
            assert call_args[0][0] == "error"
            assert "Test error" in call_args[0][2]


class TestPipelineStageSelection:
    """Tests for pipeline stage selection logic."""
    
    def test_only_collection_enabled(self):
        """Test only collection runs when others disabled."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            config = Mock()
            config.database_url = "postgresql://test:test@localhost/test"
            config.interval_minutes = 5
            config.timeframes = ["1h"]
            config.enable_collection = True
            config.enable_normalization = False
            config.enable_whale_detection = False
            config.enable_smart_wallet = False
            config.enable_signal_engine = False
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=config)
            
            # Mock all stage methods
            scheduler._run_collection = Mock()
            scheduler._run_normalization = Mock()
            scheduler._run_whale_detection = Mock()
            scheduler._run_smart_wallet_classification = Mock()
            scheduler._run_signal_generation = Mock()
            scheduler._update_scheduler_state = Mock()
            
            scheduler.run_pipeline()
            
            scheduler._run_collection.assert_called_once()
            scheduler._run_normalization.assert_not_called()
            scheduler._run_whale_detection.assert_not_called()
            scheduler._run_smart_wallet_classification.assert_not_called()
            scheduler._run_signal_generation.assert_not_called()
    
    def test_only_signal_engine_enabled(self):
        """Test only signal engine runs when others disabled."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            config = Mock()
            config.database_url = "postgresql://test:test@localhost/test"
            config.interval_minutes = 5
            config.timeframes = ["1h"]
            config.enable_collection = False
            config.enable_normalization = False
            config.enable_whale_detection = False
            config.enable_smart_wallet = False
            config.enable_signal_engine = True
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=config)
            
            # Mock all stage methods
            scheduler._run_collection = Mock()
            scheduler._run_normalization = Mock()
            scheduler._run_whale_detection = Mock()
            scheduler._run_smart_wallet_classification = Mock()
            scheduler._run_signal_generation = Mock()
            scheduler._update_scheduler_state = Mock()
            
            scheduler.run_pipeline()
            
            scheduler._run_collection.assert_not_called()
            scheduler._run_normalization.assert_not_called()
            scheduler._run_whale_detection.assert_not_called()
            scheduler._run_smart_wallet_classification.assert_not_called()
            scheduler._run_signal_generation.assert_called_once()
    
    def test_all_stages_run_in_order(self):
        """Test all stages run when all enabled."""
        import onchain_intel_product.scheduler as scheduler_module
        
        with patch.object(scheduler_module, 'create_engine'), \
             patch.object(scheduler_module, 'sessionmaker'), \
             patch('signal.signal'):
            
            config = Mock()
            config.database_url = "postgresql://test:test@localhost/test"
            config.interval_minutes = 5
            config.timeframes = ["1h"]
            config.enable_collection = True
            config.enable_normalization = True
            config.enable_whale_detection = True
            config.enable_smart_wallet = True
            config.enable_signal_engine = True
            
            scheduler = scheduler_module.OnChainPipelineScheduler(config=config)
            
            # Mock all stage methods
            scheduler._run_collection = Mock()
            scheduler._run_normalization = Mock()
            scheduler._run_whale_detection = Mock()
            scheduler._run_smart_wallet_classification = Mock()
            scheduler._run_signal_generation = Mock()
            scheduler._update_scheduler_state = Mock()
            
            scheduler.run_pipeline()
            
            scheduler._run_collection.assert_called_once()
            scheduler._run_normalization.assert_called_once()
            scheduler._run_whale_detection.assert_called_once()
            scheduler._run_smart_wallet_classification.assert_called_once()
            scheduler._run_signal_generation.assert_called_once()
