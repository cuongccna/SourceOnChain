"""Threshold calculator for whale detection."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from whale_detection.models.config import WhaleDetectionConfig
from whale_detection.models.whale_data import WhaleThresholds
from whale_detection.utils.statistical_analysis import (
    calculate_rolling_percentiles,
    calculate_distribution_metrics,
    validate_threshold_quality
)

logger = structlog.get_logger(__name__)


class ThresholdCalculator:
    """Calculates dynamic whale detection thresholds using rolling percentiles."""
    
    def __init__(self, config: WhaleDetectionConfig):
        self.config = config
        self.logger = logger.bind(component="threshold_calculator")
        
        # Database connection
        self.engine = create_engine(config.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Threshold cache
        self.threshold_cache = {}
        
        self.logger.info("Threshold calculator initialized")
    
    def calculate_thresholds(self, timestamp: datetime, 
                           timeframe: str) -> Optional[WhaleThresholds]:
        """
        Calculate whale detection thresholds for a specific timestamp and timeframe.
        
        Args:
            timestamp: Target timestamp
            timeframe: Timeframe ('1h', '4h', '1d')
            
        Returns:
            WhaleThresholds object or None if calculation fails
        """
        self.logger.debug("Calculating whale thresholds",
                         timestamp=timestamp,
                         timeframe=timeframe)
        
        try:
            # Check cache first
            if self.config.enable_threshold_caching:
                cached_thresholds = self._get_cached_thresholds(timestamp, timeframe)
                if cached_thresholds:
                    return cached_thresholds
            
            # Get rolling window size
            window_hours = self.config.get_rolling_window(timeframe)
            
            # Get historical transaction data
            tx_values = self._get_historical_transaction_values(
                timestamp, timeframe, window_hours
            )
            
            if len(tx_values) < self.config.min_sample_size:
                self.logger.warning("Insufficient sample size for threshold calculation",
                                  sample_size=len(tx_values),
                                  min_required=self.config.min_sample_size)
                return None
            
            # Get historical UTXO data
            utxo_values = self._get_historical_utxo_values(
                timestamp, timeframe, window_hours
            )
            
            # Calculate transaction percentiles
            tx_percentiles = self._calculate_transaction_percentiles(tx_values)
            
            # Calculate UTXO percentiles
            utxo_percentiles = self._calculate_utxo_percentiles(utxo_values)
            
            # Calculate activity spike thresholds
            activity_thresholds = self._calculate_activity_thresholds(
                timestamp, timeframe, window_hours
            )
            
            # Validate threshold quality
            quality_metrics = self._validate_threshold_quality(tx_values, tx_percentiles)
            
            # Create WhaleThresholds object
            thresholds = WhaleThresholds(
                asset="BTC",
                timeframe=timeframe,
                calculation_timestamp=timestamp,
                calculation_window_hours=window_hours,
                
                # Transaction thresholds
                large_tx_threshold_p95=tx_percentiles['p95'],
                whale_tx_threshold_p99=tx_percentiles['p99'],
                ultra_whale_threshold_p999=tx_percentiles['p999'],
                leviathan_threshold_p9999=tx_percentiles.get('p9999'),
                
                # UTXO thresholds
                whale_utxo_threshold_p99=utxo_percentiles['p99'],
                ultra_whale_utxo_threshold_p999=utxo_percentiles['p999'],
                
                # Activity thresholds
                whale_count_spike_threshold=activity_thresholds['count_threshold'],
                whale_volume_spike_threshold=activity_thresholds['volume_threshold'],
                
                # Quality metrics
                threshold_stability_score=quality_metrics['stability_score'],
                regime_change_detected=quality_metrics['regime_change'],
                sample_size=len(tx_values),
                distribution_skewness=quality_metrics['skewness'],
                distribution_kurtosis=quality_metrics['kurtosis']
            )
            
            # Cache the thresholds
            if self.config.enable_threshold_caching:
                self._cache_thresholds(thresholds)
            
            self.logger.info("Whale thresholds calculated successfully",
                           timeframe=timeframe,
                           whale_threshold=float(thresholds.whale_tx_threshold_p99),
                           sample_size=len(tx_values),
                           stability_score=float(thresholds.threshold_stability_score or 0))
            
            return thresholds
            
        except Exception as e:
            self.logger.error("Failed to calculate whale thresholds",
                            timestamp=timestamp,
                            timeframe=timeframe,
                            error=str(e))
            return None
    
    def _get_historical_transaction_values(self, timestamp: datetime, 
                                         timeframe: str, 
                                         window_hours: int) -> List[Decimal]:
        """Get historical transaction values for threshold calculation."""
        
        start_time = timestamp - timedelta(hours=window_hours)
        
        with self.SessionLocal() as session:
            # Query transaction values from the specified time window
            result = session.execute(text("""
                SELECT t.total_output_btc
                FROM transactions t
                JOIN blocks b ON t.block_height = b.block_height
                WHERE b.block_time >= :start_time 
                    AND b.block_time < :end_time
                    AND t.is_coinbase = FALSE
                    AND t.total_output_btc > 0
                ORDER BY t.total_output_btc
            """), {
                "start_time": start_time,
                "end_time": timestamp
            }).fetchall()
            
            return [Decimal(str(row[0])) for row in result]
    
    def _get_historical_utxo_values(self, timestamp: datetime,
                                   timeframe: str,
                                   window_hours: int) -> List[Decimal]:
        """Get historical UTXO values for threshold calculation."""
        
        start_time = timestamp - timedelta(hours=window_hours)
        
        with self.SessionLocal() as session:
            result = session.execute(text("""
                SELECT u.value_btc
                FROM utxos u
                JOIN transactions t ON u.tx_hash = t.tx_hash
                JOIN blocks b ON t.block_height = b.block_height
                WHERE b.block_time >= :start_time 
                    AND b.block_time < :end_time
                    AND u.value_btc > 0
                ORDER BY u.value_btc
            """), {
                "start_time": start_time,
                "end_time": timestamp
            }).fetchall()
            
            return [Decimal(str(row[0])) for row in result]
    
    def _calculate_transaction_percentiles(self, tx_values: List[Decimal]) -> Dict[str, Decimal]:
        """Calculate transaction value percentiles."""
        
        percentiles_to_calc = [
            self.config.large_tx_percentile,
            self.config.whale_tx_percentile,
            self.config.ultra_whale_percentile,
            self.config.leviathan_percentile
        ]
        
        float_values = [float(v) for v in tx_values]
        
        import numpy as np
        
        result = {}
        for p in percentiles_to_calc:
            percentile_value = np.percentile(float_values, p)
            
            if p == self.config.large_tx_percentile:
                result['p95'] = Decimal(str(round(percentile_value, 8)))
            elif p == self.config.whale_tx_percentile:
                result['p99'] = Decimal(str(round(percentile_value, 8)))
            elif p == self.config.ultra_whale_percentile:
                result['p999'] = Decimal(str(round(percentile_value, 8)))
            elif p == self.config.leviathan_percentile:
                result['p9999'] = Decimal(str(round(percentile_value, 8)))
        
        return result
    
    def _calculate_utxo_percentiles(self, utxo_values: List[Decimal]) -> Dict[str, Decimal]:
        """Calculate UTXO value percentiles."""
        
        if not utxo_values:
            return {
                'p99': Decimal('0'),
                'p999': Decimal('0')
            }
        
        float_values = [float(v) for v in utxo_values]
        
        import numpy as np
        
        p99_value = np.percentile(float_values, 99.0)
        p999_value = np.percentile(float_values, 99.9)
        
        return {
            'p99': Decimal(str(round(p99_value, 8))),
            'p999': Decimal(str(round(p999_value, 8)))
        }
    
    def _calculate_activity_thresholds(self, timestamp: datetime,
                                     timeframe: str,
                                     window_hours: int) -> Dict[str, Decimal]:
        """Calculate activity spike thresholds."""
        
        start_time = timestamp - timedelta(hours=window_hours)
        
        with self.SessionLocal() as session:
            # Get historical whale transaction counts and volumes
            # This is a simplified version - in practice, you'd query from whale_tx_ts
            result = session.execute(text("""
                SELECT 
                    DATE_TRUNC(:timeframe_interval, b.block_time) as time_bucket,
                    COUNT(*) as tx_count,
                    SUM(t.total_output_btc) as total_volume
                FROM transactions t
                JOIN blocks b ON t.block_height = b.block_height
                WHERE b.block_time >= :start_time 
                    AND b.block_time < :end_time
                    AND t.is_coinbase = FALSE
                GROUP BY time_bucket
                ORDER BY time_bucket
            """), {
                "start_time": start_time,
                "end_time": timestamp,
                "timeframe_interval": 'hour' if timeframe == '1h' else 'day'
            }).fetchall()
            
            if not result:
                return {
                    'count_threshold': Decimal('0'),
                    'volume_threshold': Decimal('0')
                }
            
            counts = [row[1] for row in result]
            volumes = [Decimal(str(row[2])) for row in result]
            
            # Calculate spike thresholds using mean + (z_threshold * std)
            import numpy as np
            
            if len(counts) > 1:
                count_mean = np.mean(counts)
                count_std = np.std(counts)
                count_threshold = count_mean + (self.config.activity_spike_zscore_threshold * count_std)
            else:
                count_threshold = 0
            
            if len(volumes) > 1:
                volume_values = [float(v) for v in volumes]
                volume_mean = np.mean(volume_values)
                volume_std = np.std(volume_values)
                volume_threshold = volume_mean + (self.config.volume_spike_zscore_threshold * volume_std)
            else:
                volume_threshold = 0
            
            return {
                'count_threshold': Decimal(str(round(count_threshold, 2))),
                'volume_threshold': Decimal(str(round(volume_threshold, 8)))
            }
    
    def _validate_threshold_quality(self, tx_values: List[Decimal],
                                   percentiles: Dict[str, Decimal]) -> Dict[str, any]:
        """Validate quality of calculated thresholds."""
        
        # Calculate distribution metrics
        dist_metrics = calculate_distribution_metrics(tx_values)
        
        # Calculate stability score (simplified)
        # In practice, this would use historical threshold series
        stability_score = 0.8  # Placeholder
        
        # Detect regime change (simplified)
        regime_change = False  # Placeholder
        
        return {
            'stability_score': Decimal(str(stability_score)),
            'regime_change': regime_change,
            'skewness': Decimal(str(round(dist_metrics['skewness'], 4))),
            'kurtosis': Decimal(str(round(dist_metrics['kurtosis'], 4)))
        }
    
    def _get_cached_thresholds(self, timestamp: datetime, 
                             timeframe: str) -> Optional[WhaleThresholds]:
        """Get cached thresholds if still valid."""
        
        cache_key = f"{timestamp.date()}_{timeframe}"
        
        if cache_key in self.threshold_cache:
            cached_data, cached_time = self.threshold_cache[cache_key]
            
            # Check if cache is still valid
            if datetime.now() - cached_time < timedelta(hours=self.config.threshold_cache_ttl_hours):
                return cached_data
        
        return None
    
    def _cache_thresholds(self, thresholds: WhaleThresholds):
        """Cache calculated thresholds."""
        
        cache_key = f"{thresholds.calculation_timestamp.date()}_{thresholds.timeframe}"
        self.threshold_cache[cache_key] = (thresholds, datetime.now())
        
        # Cleanup old cache entries (keep only last 100)
        if len(self.threshold_cache) > 100:
            oldest_key = min(self.threshold_cache.keys(), 
                           key=lambda k: self.threshold_cache[k][1])
            del self.threshold_cache[oldest_key]
    
    def get_threshold_history(self, timeframe: str, 
                            days_back: int = 30) -> List[WhaleThresholds]:
        """Get historical threshold data for analysis."""
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        # In practice, this would query the whale_thresholds_cache table
        # For now, return empty list
        return []
    
    def close(self):
        """Close database connections."""
        self.engine.dispose()
        self.logger.info("Threshold calculator connections closed")