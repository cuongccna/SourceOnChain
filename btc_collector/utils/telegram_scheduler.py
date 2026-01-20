"""
Telegram Scheduled Reports.

Automatically sends periodic reports to Telegram channel.
"""

import os
import asyncio
from datetime import datetime, time
from typing import Optional
import structlog

from .telegram import get_telegram_alerter, AlertLevel, TelegramAlerter

logger = structlog.get_logger(__name__)


class TelegramScheduler:
    """
    Schedules periodic Telegram reports.
    
    Features:
    - Periodic OnChain report (configurable interval)
    - Daily summary at specific time
    - State change alerts
    - Whale activity alerts (when threshold exceeded)
    """
    
    def __init__(
        self,
        report_interval_minutes: int = 60,  # Every hour by default
        daily_summary_hour: int = 8,        # 8 AM UTC by default
        whale_threshold_btc: float = 1000,  # Alert when net flow > 1000 BTC
        enabled: bool = True
    ):
        self.report_interval = report_interval_minutes * 60  # Convert to seconds
        self.daily_summary_hour = daily_summary_hour
        self.whale_threshold = whale_threshold_btc
        self.enabled = enabled
        
        self.alerter: Optional[TelegramAlerter] = None
        self._running = False
        self._tasks = []
        
        # Track last values for change detection
        self._last_state: Optional[str] = None
        self._last_net_flow: float = 0
        self._last_daily_summary: Optional[datetime] = None
        
        # Data fetcher callback (set by API server)
        self._get_context_fn = None
        self._get_stats_fn = None
        
    def set_data_callbacks(self, get_context_fn, get_stats_fn=None):
        """Set callbacks to fetch data from API server."""
        self._get_context_fn = get_context_fn
        self._get_stats_fn = get_stats_fn
    
    async def start(self):
        """Start the scheduler."""
        self.alerter = get_telegram_alerter()
        
        if not self.alerter.config.enabled:
            logger.warning("Telegram not configured, scheduler disabled")
            self.enabled = False
            return
        
        if not self.enabled:
            logger.info("Telegram scheduler disabled")
            return
        
        self._running = True
        logger.info("Starting Telegram scheduler", 
                   report_interval_min=self.report_interval // 60)
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._periodic_report_loop()),
            asyncio.create_task(self._daily_summary_loop()),
        ]
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks = []
        logger.info("Telegram scheduler stopped")
    
    async def _periodic_report_loop(self):
        """Send periodic OnChain reports."""
        while self._running:
            try:
                await asyncio.sleep(self.report_interval)
                
                if self._get_context_fn:
                    await self._send_periodic_report()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic report", error=str(e))
    
    async def _daily_summary_loop(self):
        """Send daily summary at specific hour."""
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Calculate next run time
                target_time = now.replace(
                    hour=self.daily_summary_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
                
                if target_time <= now:
                    # Already passed today, schedule for tomorrow
                    from datetime import timedelta
                    target_time += timedelta(days=1)
                
                # Sleep until target time
                sleep_seconds = (target_time - now).total_seconds()
                logger.debug("Daily summary scheduled", 
                            target=target_time.isoformat(),
                            sleep_seconds=sleep_seconds)
                
                await asyncio.sleep(sleep_seconds)
                
                if self._running and self._get_stats_fn:
                    await self._send_daily_summary()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in daily summary", error=str(e))
    
    async def _send_periodic_report(self):
        """Send periodic OnChain report."""
        try:
            if not self._get_context_fn:
                return
            
            context = await self._get_context_fn()
            if not context:
                return
            
            # Check for state change
            current_state = context.get('state', 'UNKNOWN')
            if self._last_state and current_state != self._last_state:
                # State changed! Send alert
                await self.alerter.send_state_change_alert(
                    self._last_state, 
                    current_state,
                    context.get('usage_policy', {}).get('notes')
                )
            self._last_state = current_state
            
            # Check for significant whale activity
            whale = context.get('metrics', {}).get('whale', {})
            net_flow = whale.get('net_whale_flow', 0)
            
            if abs(net_flow) > self.whale_threshold and abs(net_flow - self._last_net_flow) > self.whale_threshold / 2:
                # Significant whale activity
                whale_data = {
                    'behavior': 'ACCUMULATION' if net_flow > 0 else 'DISTRIBUTION',
                    'description': f'Significant whale movement: {net_flow:+,.2f} BTC net flow',
                    'metrics': {
                        'net_flow_btc': net_flow,
                        'whale_volume_btc': whale.get('whale_volume_btc', 0),
                        'whale_tx_count': whale.get('whale_tx_count', 0),
                        'dominance_ratio': whale.get('whale_dominance', 0)
                    }
                }
                await self.alerter.send_whale_alert(whale_data)
            self._last_net_flow = net_flow
            
            # Send regular report
            await self.alerter.send_onchain_report(context)
            logger.info("Periodic report sent")
            
        except Exception as e:
            logger.error("Failed to send periodic report", error=str(e))
    
    async def _send_daily_summary(self):
        """Send daily summary."""
        try:
            if not self._get_stats_fn:
                return
            
            stats = await self._get_stats_fn()
            if stats:
                await self.alerter.send_daily_summary(stats)
                self._last_daily_summary = datetime.utcnow()
                logger.info("Daily summary sent")
                
        except Exception as e:
            logger.error("Failed to send daily summary", error=str(e))


# Configuration from environment
def get_scheduler_config() -> dict:
    """Get scheduler configuration from environment."""
    return {
        'report_interval_minutes': int(os.getenv('TELEGRAM_REPORT_INTERVAL_MIN', '60')),
        'daily_summary_hour': int(os.getenv('TELEGRAM_DAILY_SUMMARY_HOUR', '8')),
        'whale_threshold_btc': float(os.getenv('TELEGRAM_WHALE_ALERT_THRESHOLD', '1000')),
        'enabled': os.getenv('TELEGRAM_SCHEDULER_ENABLED', 'true').lower() == 'true'
    }


# Singleton instance
_scheduler: Optional[TelegramScheduler] = None


def get_telegram_scheduler() -> TelegramScheduler:
    """Get or create scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        config = get_scheduler_config()
        _scheduler = TelegramScheduler(**config)
    return _scheduler
