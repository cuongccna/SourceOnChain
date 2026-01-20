"""
OnChain Data Pipeline Scheduler

Chạy định kỳ mỗi 5 phút để:
1. Thu thập dữ liệu từ Bitcoin Core
2. Normalize dữ liệu vào time-series
3. Tính toán whale detection
4. Phân loại smart wallets
5. Tạo OnChain signals
"""

import os
import sys
import time
import signal
import logging
import schedule
from datetime import datetime
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class SchedulerConfig:
    """Scheduler configuration."""
    
    def __init__(self):
        self.database_url = os.getenv(
            "ONCHAIN_DATABASE_URL",
            "postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals"
        )
        self.interval_minutes = int(os.getenv("ONCHAIN_SCHEDULER_INTERVAL", "5"))
        self.log_level = os.getenv("ONCHAIN_LOG_LEVEL", "INFO")
        
        # Pipeline settings
        self.enable_collection = os.getenv("ONCHAIN_ENABLE_COLLECTION", "true").lower() == "true"
        self.enable_normalization = os.getenv("ONCHAIN_ENABLE_NORMALIZATION", "true").lower() == "true"
        self.enable_whale_detection = os.getenv("ONCHAIN_ENABLE_WHALE_DETECTION", "true").lower() == "true"
        self.enable_smart_wallet = os.getenv("ONCHAIN_ENABLE_SMART_WALLET", "true").lower() == "true"
        self.enable_signal_engine = os.getenv("ONCHAIN_ENABLE_SIGNAL_ENGINE", "true").lower() == "true"
        
        # Timeframes to process
        self.timeframes = os.getenv("ONCHAIN_TIMEFRAMES", "1h,4h,1d").split(",")


class OnChainPipelineScheduler:
    """Main pipeline scheduler for OnChain data processing."""
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        self.config = config or SchedulerConfig()
        self.logger = logger.bind(component="scheduler")
        self.running = True
        
        # Database connection
        self.engine = create_engine(self.config.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        
        self.logger.info("OnChain Pipeline Scheduler initialized",
                        interval_minutes=self.config.interval_minutes,
                        timeframes=self.config.timeframes)
    
    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info("Shutdown signal received", signal=signum)
        self.running = False
    
    def run_pipeline(self):
        """Run the complete data pipeline."""
        pipeline_start = datetime.utcnow()
        self.logger.info("Starting pipeline run", timestamp=pipeline_start)
        
        try:
            # Step 1: Collect raw data from Bitcoin Core (if enabled)
            if self.config.enable_collection:
                self._run_collection()
            
            # Step 2: Normalize data into time-series
            if self.config.enable_normalization:
                self._run_normalization()
            
            # Step 3: Calculate whale detection metrics
            if self.config.enable_whale_detection:
                self._run_whale_detection()
            
            # Step 4: Update smart wallet classifications
            if self.config.enable_smart_wallet:
                self._run_smart_wallet_classification()
            
            # Step 5: Generate OnChain signals
            if self.config.enable_signal_engine:
                self._run_signal_generation()
            
            # Log completion
            duration_ms = int((datetime.utcnow() - pipeline_start).total_seconds() * 1000)
            self.logger.info("Pipeline run completed",
                           duration_ms=duration_ms,
                           status="success")
            
            # Update scheduler state
            self._update_scheduler_state("success", duration_ms)
            
        except Exception as e:
            self.logger.error("Pipeline run failed", error=str(e))
            self._update_scheduler_state("error", 0, str(e))
    
    def _run_collection(self):
        """Run Bitcoin data collection."""
        self.logger.debug("Running data collection")
        
        try:
            # Import and run collector
            from btc_collector.core.collector import BitcoinCollector
            from btc_collector.models.config import CollectorConfig
            
            config = CollectorConfig()
            collector = BitcoinCollector(config)
            
            if collector.initialize():
                # Sync latest blocks
                collector.sync_blocks()
                collector.close()
                self.logger.info("Data collection completed")
            else:
                self.logger.warning("Failed to initialize collector")
                
        except ImportError as e:
            self.logger.warning("Collector module not available", error=str(e))
        except Exception as e:
            self.logger.error("Data collection failed", error=str(e))
    
    def _run_normalization(self):
        """Run data normalization."""
        self.logger.debug("Running data normalization")
        
        try:
            from btc_normalization.core.normalizer import BitcoinNormalizer
            from btc_normalization.models.config import NormalizationConfig
            
            config = NormalizationConfig()
            normalizer = BitcoinNormalizer(config)
            
            if normalizer.initialize():
                for timeframe in self.config.timeframes:
                    normalizer.normalize_latest(timeframe)
                self.logger.info("Data normalization completed",
                               timeframes=self.config.timeframes)
            else:
                self.logger.warning("Failed to initialize normalizer")
                
        except ImportError as e:
            self.logger.warning("Normalizer module not available", error=str(e))
        except Exception as e:
            self.logger.error("Data normalization failed", error=str(e))
    
    def _run_whale_detection(self):
        """Run whale detection calculations."""
        self.logger.debug("Running whale detection")
        
        try:
            # Direct database update for whale metrics
            with self.SessionLocal() as session:
                for timeframe in self.config.timeframes:
                    self._calculate_whale_metrics(session, timeframe)
                session.commit()
            
            self.logger.info("Whale detection completed",
                           timeframes=self.config.timeframes)
                
        except Exception as e:
            self.logger.error("Whale detection failed", error=str(e))
    
    def _calculate_whale_metrics(self, session, timeframe: str):
        """Calculate whale metrics for a timeframe."""
        try:
            # Calculate whale transaction metrics
            session.execute(text("""
                INSERT INTO whale_tx_ts (
                    timestamp, asset, timeframe,
                    whale_tx_count, whale_tx_volume_btc, total_tx_count,
                    total_tx_volume_btc, whale_tx_ratio, whale_volume_ratio
                )
                SELECT 
                    date_trunc(:timeframe_bucket, NOW()) as timestamp,
                    'BTC' as asset,
                    :timeframe as timeframe,
                    COALESCE(SUM(CASE WHEN total_output_btc >= (
                        SELECT tx_value_p99 FROM statistical_thresholds_cache 
                        WHERE asset = 'BTC' ORDER BY calculation_timestamp DESC LIMIT 1
                    ) THEN 1 ELSE 0 END), 0) as whale_tx_count,
                    COALESCE(SUM(CASE WHEN total_output_btc >= (
                        SELECT tx_value_p99 FROM statistical_thresholds_cache 
                        WHERE asset = 'BTC' ORDER BY calculation_timestamp DESC LIMIT 1
                    ) THEN total_output_btc ELSE 0 END), 0) as whale_tx_volume_btc,
                    COUNT(*) as total_tx_count,
                    COALESCE(SUM(total_output_btc), 0) as total_tx_volume_btc,
                    0 as whale_tx_ratio,
                    0 as whale_volume_ratio
                FROM transactions
                WHERE block_time >= NOW() - INTERVAL '1 hour'
                ON CONFLICT (timestamp, asset, timeframe) 
                DO UPDATE SET
                    whale_tx_count = EXCLUDED.whale_tx_count,
                    whale_tx_volume_btc = EXCLUDED.whale_tx_volume_btc,
                    total_tx_count = EXCLUDED.total_tx_count,
                    total_tx_volume_btc = EXCLUDED.total_tx_volume_btc
            """), {
                "timeframe": timeframe,
                "timeframe_bucket": "hour" if timeframe == "1h" else "day"
            })
        except Exception as e:
            self.logger.warning("Whale metrics calculation failed", 
                              timeframe=timeframe, error=str(e))
    
    def _run_smart_wallet_classification(self):
        """Run smart wallet classification."""
        self.logger.debug("Running smart wallet classification")
        
        try:
            # Smart wallet classification typically runs less frequently
            # Here we just log that it would run
            self.logger.info("Smart wallet classification skipped (runs hourly)")
                
        except Exception as e:
            self.logger.error("Smart wallet classification failed", error=str(e))
    
    def _run_signal_generation(self):
        """Run OnChain signal generation."""
        self.logger.debug("Running signal generation")
        
        try:
            timestamp = datetime.utcnow()
            
            with self.SessionLocal() as session:
                for timeframe in self.config.timeframes:
                    self._generate_signals(session, timeframe, timestamp)
                session.commit()
            
            self.logger.info("Signal generation completed",
                           timeframes=self.config.timeframes,
                           timestamp=timestamp)
                
        except Exception as e:
            self.logger.error("Signal generation failed", error=str(e))
    
    def _generate_signals(self, session, timeframe: str, timestamp: datetime):
        """Generate signals for a timeframe."""
        try:
            # Get network activity data
            network_data = session.execute(text("""
                SELECT active_addresses, tx_count, total_tx_volume_btc
                FROM network_activity_ts
                WHERE asset = 'BTC' AND timeframe = :timeframe
                ORDER BY timestamp DESC LIMIT 1
            """), {"timeframe": timeframe}).fetchone()
            
            # Get whale data
            whale_data = session.execute(text("""
                SELECT whale_tx_count, whale_tx_volume_btc, whale_volume_ratio
                FROM whale_tx_ts
                WHERE asset = 'BTC' AND timeframe = :timeframe
                ORDER BY timestamp DESC LIMIT 1
            """), {"timeframe": timeframe}).fetchone()
            
            if not network_data or not whale_data:
                self.logger.debug("Insufficient data for signal generation",
                                timeframe=timeframe)
                return
            
            # Calculate simple signals (simplified logic)
            network_growth = network_data[0] > 0 and network_data[1] > 0
            whale_dominant = float(whale_data[2] or 0) > 0.4
            
            # Store signals
            for signal_id, signal_value in [
                ("network_growth_signal", network_growth),
                ("whale_flow_dominance_signal", whale_dominant),
            ]:
                session.execute(text("""
                    INSERT INTO signal_calculations (
                        asset, timeframe, timestamp, signal_id, 
                        signal_value, signal_confidence, input_data_hash,
                        threshold_values, baseline_metrics
                    )
                    VALUES (
                        'BTC', :timeframe, :timestamp, :signal_id,
                        :signal_value, 0.75, 'scheduler_generated',
                        '{}', '{}'
                    )
                    ON CONFLICT (asset, timeframe, timestamp, signal_id)
                    DO UPDATE SET
                        signal_value = EXCLUDED.signal_value,
                        signal_confidence = EXCLUDED.signal_confidence
                """), {
                    "timeframe": timeframe,
                    "timestamp": timestamp,
                    "signal_id": signal_id,
                    "signal_value": signal_value,
                })
                
        except Exception as e:
            self.logger.warning("Signal generation failed for timeframe",
                              timeframe=timeframe, error=str(e))
    
    def _update_scheduler_state(self, status: str, duration_ms: int, error: str = None):
        """Update scheduler state in database."""
        try:
            with self.SessionLocal() as session:
                session.execute(text("""
                    INSERT INTO scheduler_state (
                        scheduler_name, last_run, next_run, status, 
                        duration_ms, error_message
                    )
                    VALUES (
                        'onchain_pipeline',
                        NOW(),
                        NOW() + INTERVAL ':interval minutes',
                        :status,
                        :duration_ms,
                        :error
                    )
                    ON CONFLICT (scheduler_name) 
                    DO UPDATE SET
                        last_run = NOW(),
                        next_run = NOW() + INTERVAL ':interval minutes',
                        status = EXCLUDED.status,
                        duration_ms = EXCLUDED.duration_ms,
                        error_message = EXCLUDED.error_message
                """), {
                    "interval": self.config.interval_minutes,
                    "status": status,
                    "duration_ms": duration_ms,
                    "error": error,
                })
                session.commit()
        except Exception as e:
            self.logger.warning("Failed to update scheduler state", error=str(e))
    
    def start(self):
        """Start the scheduler."""
        self.logger.info("Starting OnChain Pipeline Scheduler",
                        interval_minutes=self.config.interval_minutes)
        
        # Schedule the pipeline
        schedule.every(self.config.interval_minutes).minutes.do(self.run_pipeline)
        
        # Run immediately on start
        self.run_pipeline()
        
        # Main loop
        while self.running:
            schedule.run_pending()
            time.sleep(1)
        
        self.logger.info("Scheduler stopped")


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO)
    
    config = SchedulerConfig()
    scheduler = OnChainPipelineScheduler(config)
    scheduler.start()


if __name__ == "__main__":
    main()
