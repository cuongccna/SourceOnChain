"""Main Bitcoin normalization orchestrator."""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog

from btc_normalization.models.config import NormalizationConfig
from btc_normalization.core.database_manager import NormalizedDatabaseManager
from btc_normalization.core.aggregator import TimeSeriesAggregator
from btc_normalization.models.normalized_data import NormalizationResult
from btc_normalization.utils.time_utils import (
    normalize_timestamp, get_timeframe_boundaries, generate_timeframe_range
)

logger = structlog.get_logger(__name__)


class BitcoinNormalizer:
    """Main Bitcoin blockchain data normalizer."""
    
    def __init__(self, config: NormalizationConfig):
        self.config = config
        self.logger = logger.bind(component="bitcoin_normalizer")
        
        # Initialize components
        self.db_manager = NormalizedDatabaseManager(config)
        self.aggregator = TimeSeriesAggregator(config, self.db_manager)
        
        self.logger.info("Bitcoin normalizer initialized")
    
    def initialize(self) -> bool:
        """Initialize the normalizer and verify connections."""
        self.logger.info("Initializing Bitcoin normalizer...")
        
        # Test database connection
        if not self.db_manager.test_connection():
            self.logger.error("Failed to connect to database")
            return False
        
        # Validate configuration
        if not self.config.validate_timeframes():
            self.logger.error("Invalid timeframe configuration")
            return False
        
        self.logger.info("Bitcoin normalizer initialized successfully")
        return True
    
    def get_normalization_status(self) -> Dict[str, Any]:
        """Get current normalization status for all timeframes."""
        status = {}
        
        for timeframe in self.config.timeframes:
            state = self.db_manager.get_normalization_state("BTC", timeframe)
            
            if state:
                status[timeframe] = {
                    'last_normalized_timestamp': state['last_normalized_timestamp'],
                    'last_processed_block_height': state['last_processed_block_height'],
                    'is_normalizing': state['is_normalizing'],
                    'normalization_started_at': state['normalization_started_at'],
                    'normalization_completed_at': state['normalization_completed_at']
                }
            else:
                status[timeframe] = {
                    'last_normalized_timestamp': None,
                    'last_processed_block_height': 0,
                    'is_normalizing': False,
                    'normalization_started_at': None,
                    'normalization_completed_at': None
                }
        
        return status
    
    def normalize_timeframe_range(self, timeframe: str, 
                                start_time: datetime, end_time: datetime) -> bool:
        """
        Normalize data for a specific timeframe range.
        
        Args:
            timeframe: Timeframe to normalize ('1h', '4h', '1d')
            start_time: Start of normalization range
            end_time: End of normalization range
            
        Returns:
            True if normalization succeeded
        """
        self.logger.info("Starting timeframe normalization",
                        timeframe=timeframe,
                        start_time=start_time,
                        end_time=end_time)
        
        try:
            # Generate timestamps for the range
            timestamps = generate_timeframe_range(start_time, end_time, timeframe)
            
            if not timestamps:
                self.logger.warning("No timestamps to process", timeframe=timeframe)
                return True
            
            # Mark normalization as started
            self.db_manager.update_normalization_state(
                asset="BTC",
                timeframe=timeframe,
                timestamp=timestamps[0],
                block_height=0,  # Will be updated with actual block height
                is_normalizing=True
            )
            
            # Process timestamps in batches
            batch_size = min(self.config.batch_size_hours, len(timestamps))
            success_count = 0
            
            for i in range(0, len(timestamps), batch_size):
                batch_timestamps = timestamps[i:i + batch_size]
                
                self.logger.info("Processing batch",
                               timeframe=timeframe,
                               batch_start=batch_timestamps[0],
                               batch_end=batch_timestamps[-1],
                               batch_size=len(batch_timestamps))
                
                # Process batch
                batch_success = self._process_timestamp_batch(timeframe, batch_timestamps)
                
                if batch_success:
                    success_count += len(batch_timestamps)
                    
                    # Update state with last processed timestamp
                    self.db_manager.update_normalization_state(
                        asset="BTC",
                        timeframe=timeframe,
                        timestamp=batch_timestamps[-1],
                        block_height=0,  # Would be updated with actual block height
                        is_normalizing=True
                    )
                else:
                    self.logger.error("Batch processing failed",
                                    timeframe=timeframe,
                                    batch_start=batch_timestamps[0])
                    break
                
                # Small delay between batches
                time.sleep(0.1)
            
            # Mark normalization as completed
            self.db_manager.update_normalization_state(
                asset="BTC",
                timeframe=timeframe,
                timestamp=timestamps[-1],
                block_height=0,
                is_normalizing=False
            )
            
            success_ratio = success_count / len(timestamps)
            self.logger.info("Timeframe normalization completed",
                           timeframe=timeframe,
                           total_timestamps=len(timestamps),
                           successful=success_count,
                           success_ratio=f"{success_ratio:.2%}")
            
            return success_ratio > 0.95  # Consider successful if >95% processed
            
        except Exception as e:
            self.logger.error("Timeframe normalization failed",
                            timeframe=timeframe,
                            error=str(e))
            
            # Mark as not normalizing on error
            try:
                self.db_manager.update_normalization_state(
                    asset="BTC",
                    timeframe=timeframe,
                    timestamp=start_time,
                    block_height=0,
                    is_normalizing=False
                )
            except:
                pass
            
            return False
    
    def _process_timestamp_batch(self, timeframe: str, 
                               timestamps: List[datetime]) -> bool:
        """Process a batch of timestamps for normalization."""
        try:
            results = []
            
            for timestamp in timestamps:
                result = self.aggregator.aggregate_timeframe_data(timestamp, timeframe)
                results.append(result)
                
                if not result.success:
                    self.logger.warning("Failed to aggregate timestamp",
                                      timeframe=timeframe,
                                      timestamp=timestamp,
                                      error=result.error_message)
            
            # Check batch success rate
            successful = sum(1 for r in results if r.success)
            success_rate = successful / len(results) if results else 0
            
            return success_rate > 0.8  # Consider batch successful if >80% processed
            
        except Exception as e:
            self.logger.error("Batch processing error",
                            timeframe=timeframe,
                            error=str(e))
            return False
    
    def normalize_all_timeframes(self, start_time: datetime, 
                               end_time: datetime) -> Dict[str, bool]:
        """
        Normalize data for all configured timeframes.
        
        Args:
            start_time: Start of normalization range
            end_time: End of normalization range
            
        Returns:
            Dictionary mapping timeframes to success status
        """
        results = {}
        
        if self.config.enable_parallel_processing:
            # Process timeframes in parallel
            with ThreadPoolExecutor(max_workers=len(self.config.timeframes)) as executor:
                future_to_timeframe = {
                    executor.submit(self.normalize_timeframe_range, tf, start_time, end_time): tf
                    for tf in self.config.timeframes
                }
                
                for future in as_completed(future_to_timeframe):
                    timeframe = future_to_timeframe[future]
                    try:
                        results[timeframe] = future.result()
                    except Exception as e:
                        self.logger.error("Parallel normalization failed",
                                        timeframe=timeframe,
                                        error=str(e))
                        results[timeframe] = False
        else:
            # Process timeframes sequentially
            for timeframe in self.config.timeframes:
                results[timeframe] = self.normalize_timeframe_range(
                    timeframe, start_time, end_time
                )
        
        return results
    
    def normalize_latest_data(self, lookback_hours: int = 24) -> Dict[str, bool]:
        """
        Normalize the latest data (last N hours).
        
        Args:
            lookback_hours: Hours to look back from current time
            
        Returns:
            Dictionary mapping timeframes to success status
        """
        end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=lookback_hours)
        
        self.logger.info("Normalizing latest data",
                        start_time=start_time,
                        end_time=end_time,
                        lookback_hours=lookback_hours)
        
        return self.normalize_all_timeframes(start_time, end_time)
    
    def normalize_single_timestamp(self, timestamp: datetime, 
                                 timeframe: str) -> NormalizationResult:
        """
        Normalize data for a single timestamp and timeframe.
        
        Args:
            timestamp: Timestamp to normalize
            timeframe: Timeframe ('1h', '4h', '1d')
            
        Returns:
            NormalizationResult object
        """
        normalized_timestamp = normalize_timestamp(timestamp, timeframe)
        
        self.logger.info("Normalizing single timestamp",
                        timestamp=normalized_timestamp,
                        timeframe=timeframe)
        
        return self.aggregator.aggregate_timeframe_data(normalized_timestamp, timeframe)
    
    def backfill_normalization(self, days_back: int = 30) -> Dict[str, bool]:
        """
        Backfill normalization for historical data.
        
        Args:
            days_back: Number of days to backfill
            
        Returns:
            Dictionary mapping timeframes to success status
        """
        end_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(days=days_back)
        
        self.logger.info("Starting backfill normalization",
                        start_time=start_time,
                        end_time=end_time,
                        days_back=days_back)
        
        return self.normalize_all_timeframes(start_time, end_time)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get normalizer statistics."""
        status = self.get_normalization_status()
        
        return {
            'normalization_status': status,
            'config': {
                'timeframes': self.config.timeframes,
                'batch_size_hours': self.config.batch_size_hours,
                'parallel_processing': self.config.enable_parallel_processing,
                'max_workers': self.config.max_workers
            }
        }
    
    def close(self):
        """Close all connections and cleanup."""
        self.logger.info("Shutting down Bitcoin normalizer...")
        
        try:
            self.db_manager.close()
            self.logger.info("Bitcoin normalizer shutdown complete")
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))