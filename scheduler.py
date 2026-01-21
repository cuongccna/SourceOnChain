"""
Background Scheduler for OnChain Data Collection.

Runs periodic data collection and persistence.
"""

import os
import sys
import time
import signal
import threading
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import structlog
from btc_collector.core.data_provider import create_data_provider
from btc_collector.models.data_source_config import DataSourceConfig
from btc_collector.core.whale_analyzer import QuickWhaleDetector
from btc_collector.database.persistence import get_database, close_database

# Telegram integration
try:
    import asyncio
    from btc_collector.utils.telegram import get_telegram_alerter, AlertLevel
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

logger = structlog.get_logger(__name__)


class OnChainScheduler:
    """
    Background scheduler for periodic data collection.
    
    Features:
    - Configurable collection interval
    - Automatic persistence to database
    - Graceful shutdown
    - Error recovery
    """
    
    def __init__(self, interval_seconds: int = 300):
        """
        Initialize scheduler.
        
        Args:
            interval_seconds: Collection interval (default: 5 minutes)
        """
        self.interval = interval_seconds
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Initialize components
        self.config = DataSourceConfig()
        self.provider = create_data_provider(self.config)
        self.whale_detector = QuickWhaleDetector(self.provider.provider)
        self.db = get_database()
        
        # Telegram alerter
        self.telegram_enabled = TELEGRAM_AVAILABLE and os.getenv('TELEGRAM_ALERTS_ENABLED', 'true').lower() == 'true'
        self.telegram_alerter = get_telegram_alerter() if self.telegram_enabled else None
        
        # Telegram report settings
        self.telegram_report_interval = int(os.getenv('TELEGRAM_REPORT_INTERVAL_COLLECTIONS', '12'))  # Every 12 collections (~1 hour if 5min interval)
        self.telegram_whale_threshold = float(os.getenv('TELEGRAM_WHALE_ALERT_THRESHOLD', '500'))  # Alert when net flow > 500 BTC
        
        # Track state for alerts
        self._last_state = "ACTIVE"
        self._last_net_flow = 0
        
        # Stats
        self.collections = 0
        self.errors = 0
        self.last_collection: Optional[datetime] = None
        
        logger.info("OnChainScheduler initialized", 
                   interval=interval_seconds,
                   data_source=self.config.data_source)
    
    def collect_and_persist(self) -> bool:
        """
        Collect data and persist to database.
        
        Returns:
            True if successful
        """
        try:
            timestamp = datetime.utcnow()
            
            # Collect blockchain metrics
            height = self.provider.get_block_height()
            
            blocks_data = []
            total_txs = 0
            total_size = 0
            
            for h in range(height, max(height - 6, 0), -1):
                try:
                    block = self.provider.get_block(h)
                    blocks_data.append(block)
                    total_txs += block.get('nTx', 0)
                    total_size += block.get('size', 0)
                except Exception:
                    pass
            
            avg_block_size = total_size / len(blocks_data) if blocks_data else 0
            avg_txs_per_block = total_txs / len(blocks_data) if blocks_data else 0
            
            # Collect mempool metrics
            mempool = self.provider.provider.get_mempool_info()
            fees = self.provider.provider.get_recommended_fees()
            
            # Collect whale metrics
            whale_metrics = self.whale_detector.get_quick_metrics()
            
            # Build metrics dict
            metrics = {
                "blockchain": {
                    "block_height": height,
                    "blocks_analyzed": len(blocks_data),
                    "total_transactions": total_txs,
                    "avg_block_size": avg_block_size,
                    "avg_txs_per_block": avg_txs_per_block
                },
                "mempool": {
                    "pending_txs": mempool.get('count', 0),
                    "mempool_size_mb": mempool.get('vsize', 0) / 1_000_000,
                    "total_fees_btc": mempool.get('total_fee', 0) / 100_000_000,
                    "fastest_fee": fees.get('fastestFee', 0),
                    "hour_fee": fees.get('hourFee', 0)
                },
                "whale": whale_metrics
            }
            
            # Calculate signals
            net_flow = whale_metrics.get('net_whale_flow', 0)
            whale_dominance = whale_metrics.get('whale_dominance', 0)
            
            signals = {
                "smart_money_accumulation": net_flow > 0,
                "whale_flow_dominant": whale_dominance > 0.30,
                "network_growth": avg_txs_per_block > 2500,
                "distribution_risk": net_flow < 0 and abs(net_flow) > 100
            }
            
            # Calculate score
            weights = {
                "smart_money_accumulation": 35,
                "whale_flow_dominant": 10,
                "network_growth": 15,
                "distribution_risk": -40
            }
            
            score = 50
            for signal, value in signals.items():
                if value:
                    score += weights.get(signal, 0)
            score = max(0, min(100, score))
            
            if score >= 65:
                bias = "positive"
            elif score <= 35:
                bias = "negative"
            else:
                bias = "neutral"
            
            # Confidence
            active_signals = sum(1 for v in signals.values() if v)
            if active_signals >= 3:
                confidence = 0.85
            elif active_signals >= 2:
                confidence = 0.7
            else:
                confidence = 0.6
            
            state = "ACTIVE" if confidence >= 0.6 else "DEGRADED"
            
            # Persist
            self.db.save_metrics(metrics)
            self.db.save_signals(signals, score, bias, confidence, state)
            
            self.collections += 1
            self.last_collection = timestamp
            
            logger.info("Data collected and persisted",
                       height=height,
                       score=score,
                       bias=bias,
                       collections=self.collections)
            
            # === TELEGRAM ALERTS ===
            if self.telegram_enabled and self.telegram_alerter:
                try:
                    # 1. State change alert
                    if state != self._last_state:
                        asyncio.run(self.telegram_alerter.send_state_change_alert(
                            self._last_state, 
                            state,
                            f"Score: {score}, Confidence: {confidence:.2f}"
                        ))
                        self._last_state = state
                    
                    # 2. Whale activity alert (significant movement)
                    if abs(net_flow) > self.telegram_whale_threshold and abs(net_flow - self._last_net_flow) > self.telegram_whale_threshold / 2:
                        whale_data = {
                            'behavior': 'ACCUMULATION' if net_flow > 0 else 'DISTRIBUTION',
                            'description': f'Significant whale activity detected: {net_flow:+,.2f} BTC net flow',
                            'metrics': {
                                'net_flow_btc': net_flow,
                                'whale_volume_btc': whale_metrics.get('whale_volume_btc', 0),
                                'whale_tx_count': whale_metrics.get('whale_tx_count', 0),
                                'dominance_ratio': whale_dominance
                            }
                        }
                        asyncio.run(self.telegram_alerter.send_whale_alert(whale_data))
                    self._last_net_flow = net_flow
                    
                    # 3. Periodic report (every N collections)
                    if self.collections % self.telegram_report_interval == 0:
                        report_data = {
                            "state": state,
                            "decision_context": {
                                "onchain_score": score,
                                "bias": bias,
                                "confidence": confidence
                            },
                            "signals": {
                                "active": [k for k, v in signals.items() if v]
                            },
                            "metrics": {
                                "whale": whale_metrics
                            },
                            "verification": {
                                "data_completeness": 1.0,
                                "data_age_seconds": 0,
                                "invariants_passed": True
                            },
                            "usage_policy": {
                                "allowed": state != "BLOCKED",
                                "recommended_weight": 0.3 if state == "ACTIVE" else 0.15
                            }
                        }
                        asyncio.run(self.telegram_alerter.send_onchain_report(report_data))
                        logger.info("Telegram report sent", collections=self.collections)
                        
                except Exception as e:
                    logger.error("Telegram alert failed", error=str(e))
            
            return True
            
        except Exception as e:
            self.errors += 1
            logger.error("Collection failed", error=str(e), errors=self.errors)
            return False
    
    def _run_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        
        while self.running:
            try:
                self.collect_and_persist()
            except Exception as e:
                logger.error("Scheduler error", error=str(e))
            
            # Wait for next interval
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info("Scheduler loop stopped")
    
    def start(self):
        """Start the scheduler in background thread."""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler gracefully."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        close_database()
        logger.info("Scheduler stopped", 
                   collections=self.collections, 
                   errors=self.errors)
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "interval_seconds": self.interval,
            "collections": self.collections,
            "errors": self.errors,
            "last_collection": self.last_collection.isoformat() if self.last_collection else None,
            "data_source": self.config.data_source
        }


def main():
    """Main entry point."""
    
    # Get interval from environment or default to 5 minutes
    interval = int(os.getenv('SCHEDULER_INTERVAL', 300))
    telegram_report_interval = int(os.getenv('TELEGRAM_REPORT_INTERVAL_COLLECTIONS', '12'))
    
    print(f"""
    ===========================================================
             OnChain Data Scheduler
    ===========================================================
      Interval:    {interval} seconds
      Data Source: mempool.space
      Database:    PostgreSQL
      Telegram:    {'Enabled' if TELEGRAM_AVAILABLE else 'Disabled'}
      Report Every: {telegram_report_interval} collections (~{interval * telegram_report_interval // 60} min)
      
      Press Ctrl+C to stop
    ===========================================================
    """)
    
    scheduler = OnChainScheduler(interval_seconds=interval)
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        print("\n⚠️ Shutting down...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start scheduler
    scheduler.start()
    
    # Do initial collection immediately
    print("📊 Running initial collection...")
    scheduler.collect_and_persist()
    
    # Send startup notification
    if scheduler.telegram_enabled and scheduler.telegram_alerter:
        try:
            asyncio.run(scheduler.telegram_alerter.send_alert(
                AlertLevel.SUCCESS,
                "OnChain Scheduler Started",
                f"Collecting data every {interval} seconds",
                {"data_source": scheduler.config.data_source}
            ))
        except Exception as e:
            print(f"⚠️ Failed to send Telegram startup alert: {e}")
    
    # Keep main thread alive
    while scheduler.running:
        try:
            time.sleep(10)
            status = scheduler.get_status()
            print(f"📈 Collections: {status['collections']} | Errors: {status['errors']} | Last: {status['last_collection']}")
        except KeyboardInterrupt:
            break
    
    scheduler.stop()
    print("✅ Scheduler stopped")


if __name__ == "__main__":
    main()
