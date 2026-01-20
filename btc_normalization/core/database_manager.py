"""Database manager for normalized data operations."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import structlog

from btc_normalization.models.config import NormalizationConfig
from btc_normalization.models.normalized_data import (
    NetworkActivityData, UTXOFlowData, AddressBehaviorData,
    ValueDistributionData, LargeTransactionData, StatisticalThresholds
)

logger = structlog.get_logger(__name__)


class NormalizedDatabaseManager:
    """Manages database operations for normalized data."""
    
    def __init__(self, config: NormalizationConfig):
        self.config = config
        self.logger = logger.bind(component="normalized_db_manager")
        
        # Create engine with connection pooling
        self.engine = create_engine(
            config.database_url,
            poolclass=QueuePool,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_pre_ping=True,
            echo=False
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        self.logger.info("Normalized database manager initialized")
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.info("Database connection successful")
            return True
        except Exception as e:
            self.logger.error("Database connection failed", error=str(e))
            return False
    
    # ============================================================================
    # NORMALIZATION STATE MANAGEMENT
    # ============================================================================
    
    def get_normalization_state(self, asset: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Get normalization state for asset-timeframe combination."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT last_normalized_timestamp, last_processed_block_height,
                       is_normalizing, normalization_started_at, normalization_completed_at
                FROM normalization_state 
                WHERE asset = :asset AND timeframe = :timeframe
            """), {"asset": asset, "timeframe": timeframe}).fetchone()
            
            if result:
                return {
                    'last_normalized_timestamp': result[0],
                    'last_processed_block_height': result[1],
                    'is_normalizing': result[2],
                    'normalization_started_at': result[3],
                    'normalization_completed_at': result[4]
                }
            return None
    
    def update_normalization_state(self, asset: str, timeframe: str, 
                                 timestamp: datetime, block_height: int,
                                 is_normalizing: bool = False):
        """Update normalization state."""
        with self.get_session() as session:
            session.execute(text("""
                INSERT INTO normalization_state 
                (asset, timeframe, last_normalized_timestamp, last_processed_block_height, is_normalizing)
                VALUES (:asset, :timeframe, :timestamp, :block_height, :is_normalizing)
                ON CONFLICT (asset, timeframe) 
                DO UPDATE SET 
                    last_normalized_timestamp = :timestamp,
                    last_processed_block_height = :block_height,
                    is_normalizing = :is_normalizing,
                    updated_at = NOW()
            """), {
                "asset": asset,
                "timeframe": timeframe, 
                "timestamp": timestamp,
                "block_height": block_height,
                "is_normalizing": is_normalizing
            })
            session.commit()
    
    # ============================================================================
    # RAW DATA QUERIES
    # ============================================================================
    
    def get_raw_transactions_in_timeframe(self, start_time: datetime, 
                                        end_time: datetime) -> List[Dict[str, Any]]:
        """Get raw transaction data for a time period."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT t.tx_hash, t.block_height, t.block_time, t.tx_index,
                       t.input_count, t.output_count, t.total_input_btc, 
                       t.total_output_btc, t.fee_btc, t.is_coinbase,
                       t.tx_size_bytes, t.tx_weight
                FROM transactions t
                WHERE t.block_time >= :start_time 
                    AND t.block_time < :end_time
                ORDER BY t.block_time, t.tx_index
            """), {"start_time": start_time, "end_time": end_time}).fetchall()
            
            return [dict(row._mapping) for row in result]
    
    def get_raw_utxos_in_timeframe(self, start_time: datetime, 
                                 end_time: datetime) -> List[Dict[str, Any]]:
        """Get raw UTXO data for a time period."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT u.tx_hash, u.vout_index, u.address, u.script_type,
                       u.value_btc, u.is_spent, u.spent_tx_hash, 
                       u.spent_block_height, u.spent_at, t.block_time as created_at
                FROM utxos u
                JOIN transactions t ON u.tx_hash = t.tx_hash
                WHERE t.block_time >= :start_time 
                    AND t.block_time < :end_time
                ORDER BY t.block_time
            """), {"start_time": start_time, "end_time": end_time}).fetchall()
            
            return [dict(row._mapping) for row in result]
    
    def get_address_activity_in_timeframe(self, start_time: datetime,
                                        end_time: datetime) -> List[Dict[str, Any]]:
        """Get address activity data for a time period."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT DISTINCT u.address, t.block_time, t.block_height,
                       SUM(u.value_btc) as total_value,
                       COUNT(*) as utxo_count
                FROM utxos u
                JOIN transactions t ON u.tx_hash = t.tx_hash
                WHERE t.block_time >= :start_time 
                    AND t.block_time < :end_time
                    AND u.address IS NOT NULL
                GROUP BY u.address, t.block_time, t.block_height
                ORDER BY t.block_time
            """), {"start_time": start_time, "end_time": end_time}).fetchall()
            
            return [dict(row._mapping) for row in result]
    
    # ============================================================================
    # STATISTICAL THRESHOLD OPERATIONS
    # ============================================================================
    
    def get_cached_thresholds(self, asset: str, window_hours: int, 
                            max_age_hours: int = 6) -> Optional[StatisticalThresholds]:
        """Get cached statistical thresholds."""
        with self.get_session() as session:
            result = session.execute(text("""
                SELECT * FROM statistical_thresholds_cache
                WHERE asset = :asset 
                    AND window_hours = :window_hours
                    AND calculation_timestamp >= NOW() - INTERVAL ':max_age hours'
                ORDER BY calculation_timestamp DESC
                LIMIT 1
            """), {
                "asset": asset,
                "window_hours": window_hours,
                "max_age": max_age_hours
            }).fetchone()
            
            if result:
                row_dict = dict(result._mapping)
                return StatisticalThresholds(
                    asset=row_dict['asset'],
                    calculation_timestamp=row_dict['calculation_timestamp'],
                    window_hours=row_dict['window_hours'],
                    tx_value_p50=row_dict.get('tx_value_p50'),
                    tx_value_p75=row_dict.get('tx_value_p75'),
                    tx_value_p90=row_dict.get('tx_value_p90'),
                    tx_value_p95=row_dict.get('tx_value_p95'),
                    tx_value_p99=row_dict.get('tx_value_p99'),
                    tx_value_p999=row_dict.get('tx_value_p999'),
                    utxo_value_p95=row_dict.get('utxo_value_p95'),
                    utxo_value_p99=row_dict.get('utxo_value_p99'),
                    fee_p95=row_dict.get('fee_p95'),
                    fee_p99=row_dict.get('fee_p99'),
                    tx_sample_size=row_dict.get('tx_sample_size'),
                    utxo_sample_size=row_dict.get('utxo_sample_size')
                )
            return None
    
    def save_statistical_thresholds(self, thresholds: StatisticalThresholds):
        """Save calculated statistical thresholds to cache."""
        with self.get_session() as session:
            session.execute(text("""
                INSERT INTO statistical_thresholds_cache 
                (asset, calculation_timestamp, window_hours, tx_value_p50, tx_value_p75,
                 tx_value_p90, tx_value_p95, tx_value_p99, tx_value_p999,
                 utxo_value_p95, utxo_value_p99, fee_p95, fee_p99,
                 tx_sample_size, utxo_sample_size)
                VALUES (:asset, :calc_time, :window_hours, :tx_p50, :tx_p75,
                        :tx_p90, :tx_p95, :tx_p99, :tx_p999,
                        :utxo_p95, :utxo_p99, :fee_p95, :fee_p99,
                        :tx_sample, :utxo_sample)
            """), {
                "asset": thresholds.asset,
                "calc_time": thresholds.calculation_timestamp,
                "window_hours": thresholds.window_hours,
                "tx_p50": thresholds.tx_value_p50,
                "tx_p75": thresholds.tx_value_p75,
                "tx_p90": thresholds.tx_value_p90,
                "tx_p95": thresholds.tx_value_p95,
                "tx_p99": thresholds.tx_value_p99,
                "tx_p999": thresholds.tx_value_p999,
                "utxo_p95": thresholds.utxo_value_p95,
                "utxo_p99": thresholds.utxo_value_p99,
                "fee_p95": thresholds.fee_p95,
                "fee_p99": thresholds.fee_p99,
                "tx_sample": thresholds.tx_sample_size,
                "utxo_sample": thresholds.utxo_sample_size
            })
            session.commit()
    
    # ============================================================================
    # NORMALIZED DATA OPERATIONS
    # ============================================================================
    
    def save_network_activity(self, data: NetworkActivityData) -> bool:
        """Save network activity data."""
        try:
            with self.get_session() as session:
                session.execute(text("""
                    INSERT INTO network_activity_ts 
                    (timestamp, asset, timeframe, active_addresses, tx_count,
                     total_tx_volume_btc, avg_tx_value_btc, median_tx_value_btc,
                     total_fees_btc, avg_fee_per_tx_btc, avg_tx_size_bytes,
                     blocks_mined, avg_block_size_bytes, avg_tx_per_block)
                    VALUES (:timestamp, :asset, :timeframe, :active_addresses, :tx_count,
                            :total_volume, :avg_value, :median_value,
                            :total_fees, :avg_fee, :avg_size,
                            :blocks, :avg_block_size, :avg_tx_per_block)
                    ON CONFLICT (timestamp, asset, timeframe) 
                    DO UPDATE SET
                        active_addresses = :active_addresses,
                        tx_count = :tx_count,
                        total_tx_volume_btc = :total_volume,
                        avg_tx_value_btc = :avg_value,
                        median_tx_value_btc = :median_value,
                        total_fees_btc = :total_fees,
                        avg_fee_per_tx_btc = :avg_fee,
                        avg_tx_size_bytes = :avg_size,
                        blocks_mined = :blocks,
                        avg_block_size_bytes = :avg_block_size,
                        avg_tx_per_block = :avg_tx_per_block
                """), {
                    "timestamp": data.timestamp,
                    "asset": data.asset,
                    "timeframe": data.timeframe,
                    "active_addresses": data.active_addresses,
                    "tx_count": data.tx_count,
                    "total_volume": data.total_tx_volume_btc,
                    "avg_value": data.avg_tx_value_btc,
                    "median_value": data.median_tx_value_btc,
                    "total_fees": data.total_fees_btc,
                    "avg_fee": data.avg_fee_per_tx_btc,
                    "avg_size": data.avg_tx_size_bytes,
                    "blocks": data.blocks_mined,
                    "avg_block_size": data.avg_block_size_bytes,
                    "avg_tx_per_block": data.avg_tx_per_block
                })
                session.commit()
                return True
        except Exception as e:
            self.logger.error("Failed to save network activity data", error=str(e))
            return False
    
    def save_utxo_flow(self, data: UTXOFlowData) -> bool:
        """Save UTXO flow data."""
        try:
            with self.get_session() as session:
                session.execute(text("""
                    INSERT INTO utxo_flow_ts 
                    (timestamp, asset, timeframe, utxo_created_count, utxo_spent_count,
                     net_utxo_change, btc_created, btc_spent, net_utxo_flow_btc,
                     utxo_created_avg_value_btc, utxo_spent_avg_value_btc,
                     avg_utxo_age_days, median_utxo_age_days,
                     coinbase_utxo_created_count, coinbase_btc_created)
                    VALUES (:timestamp, :asset, :timeframe, :created_count, :spent_count,
                            :net_change, :btc_created, :btc_spent, :net_flow,
                            :created_avg, :spent_avg, :avg_age, :median_age,
                            :coinbase_count, :coinbase_btc)
                    ON CONFLICT (timestamp, asset, timeframe)
                    DO UPDATE SET
                        utxo_created_count = :created_count,
                        utxo_spent_count = :spent_count,
                        net_utxo_change = :net_change,
                        btc_created = :btc_created,
                        btc_spent = :btc_spent,
                        net_utxo_flow_btc = :net_flow,
                        utxo_created_avg_value_btc = :created_avg,
                        utxo_spent_avg_value_btc = :spent_avg,
                        avg_utxo_age_days = :avg_age,
                        median_utxo_age_days = :median_age,
                        coinbase_utxo_created_count = :coinbase_count,
                        coinbase_btc_created = :coinbase_btc
                """), {
                    "timestamp": data.timestamp,
                    "asset": data.asset,
                    "timeframe": data.timeframe,
                    "created_count": data.utxo_created_count,
                    "spent_count": data.utxo_spent_count,
                    "net_change": data.net_utxo_change,
                    "btc_created": data.btc_created,
                    "btc_spent": data.btc_spent,
                    "net_flow": data.net_utxo_flow_btc,
                    "created_avg": data.utxo_created_avg_value_btc,
                    "spent_avg": data.utxo_spent_avg_value_btc,
                    "avg_age": data.avg_utxo_age_days,
                    "median_age": data.median_utxo_age_days,
                    "coinbase_count": data.coinbase_utxo_created_count,
                    "coinbase_btc": data.coinbase_btc_created
                })
                session.commit()
                return True
        except Exception as e:
            self.logger.error("Failed to save UTXO flow data", error=str(e))
            return False
    
    def save_large_tx_activity(self, data: LargeTransactionData) -> bool:
        """Save large transaction activity data."""
        try:
            with self.get_session() as session:
                session.execute(text("""
                    INSERT INTO large_tx_activity_ts 
                    (timestamp, asset, timeframe, large_tx_threshold_btc, large_tx_count,
                     large_tx_volume_btc, large_tx_ratio, large_tx_volume_ratio,
                     whale_tx_threshold_btc, whale_tx_count, whale_tx_volume_btc, whale_tx_ratio,
                     avg_large_tx_value_btc, max_tx_value_btc, large_tx_avg_fee_btc,
                     potential_exchange_large_tx_count, potential_exchange_large_tx_volume_btc,
                     threshold_calculation_window_hours, threshold_percentile, whale_threshold_percentile)
                    VALUES (:timestamp, :asset, :timeframe, :large_threshold, :large_count,
                            :large_volume, :large_ratio, :large_vol_ratio,
                            :whale_threshold, :whale_count, :whale_volume, :whale_ratio,
                            :avg_large_value, :max_value, :avg_large_fee,
                            :exchange_count, :exchange_volume,
                            :window_hours, :threshold_pct, :whale_pct)
                    ON CONFLICT (timestamp, asset, timeframe)
                    DO UPDATE SET
                        large_tx_threshold_btc = :large_threshold,
                        large_tx_count = :large_count,
                        large_tx_volume_btc = :large_volume,
                        large_tx_ratio = :large_ratio,
                        large_tx_volume_ratio = :large_vol_ratio,
                        whale_tx_threshold_btc = :whale_threshold,
                        whale_tx_count = :whale_count,
                        whale_tx_volume_btc = :whale_volume,
                        whale_tx_ratio = :whale_ratio,
                        avg_large_tx_value_btc = :avg_large_value,
                        max_tx_value_btc = :max_value,
                        large_tx_avg_fee_btc = :avg_large_fee,
                        potential_exchange_large_tx_count = :exchange_count,
                        potential_exchange_large_tx_volume_btc = :exchange_volume
                """), {
                    "timestamp": data.timestamp,
                    "asset": data.asset,
                    "timeframe": data.timeframe,
                    "large_threshold": data.large_tx_threshold_btc,
                    "large_count": data.large_tx_count,
                    "large_volume": data.large_tx_volume_btc,
                    "large_ratio": data.large_tx_ratio,
                    "large_vol_ratio": data.large_tx_volume_ratio,
                    "whale_threshold": data.whale_tx_threshold_btc,
                    "whale_count": data.whale_tx_count,
                    "whale_volume": data.whale_tx_volume_btc,
                    "whale_ratio": data.whale_tx_ratio,
                    "avg_large_value": data.avg_large_tx_value_btc,
                    "max_value": data.max_tx_value_btc,
                    "avg_large_fee": data.large_tx_avg_fee_btc,
                    "exchange_count": data.potential_exchange_large_tx_count,
                    "exchange_volume": data.potential_exchange_large_tx_volume_btc,
                    "window_hours": data.threshold_calculation_window_hours,
                    "threshold_pct": data.threshold_percentile,
                    "whale_pct": data.whale_threshold_percentile
                })
                session.commit()
                return True
        except Exception as e:
            self.logger.error("Failed to save large transaction data", error=str(e))
            return False
    
    def close(self):
        """Close database connections."""
        self.engine.dispose()
        self.logger.info("Normalized database connections closed")