"""
Telegram Alerting Module for OnChain Intelligence.

Sends reports and alerts to Telegram channel/group.
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "ℹ️"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    CRITICAL = "🚨"


@dataclass
class TelegramConfig:
    """Telegram configuration from environment."""
    
    bot_token: str
    channel_id: str
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        """Load config from environment variables."""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '')
        enabled = os.getenv('TELEGRAM_ALERTS_ENABLED', 'true').lower() == 'true'
        
        if not bot_token or not channel_id:
            logger.warning("Telegram not configured - alerts disabled")
            enabled = False
        
        return cls(
            bot_token=bot_token,
            channel_id=channel_id,
            enabled=enabled
        )


class TelegramAlerter:
    """
    Sends alerts and reports to Telegram.
    
    Uses Telegram Bot API (not Client API).
    """
    
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or TelegramConfig.from_env()
        self._session: Optional[aiohttp.ClientSession] = None
        
        if self.config.enabled:
            logger.info("TelegramAlerter initialized", 
                       channel_id=self.config.channel_id[:5] + "***")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _send_request(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to Telegram Bot API."""
        if not self.config.enabled:
            logger.debug("Telegram disabled, skipping send")
            return {"ok": False, "error": "disabled"}
        
        url = self.BASE_URL.format(token=self.config.bot_token, method=method)
        
        try:
            session = await self._get_session()
            async with session.post(url, json=data, timeout=30) as response:
                result = await response.json()
                
                if not result.get('ok'):
                    logger.error("Telegram API error", 
                               error=result.get('description'),
                               error_code=result.get('error_code'))
                
                return result
                
        except asyncio.TimeoutError:
            logger.error("Telegram request timeout")
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            logger.error("Telegram request failed", error=str(e))
            return {"ok": False, "error": str(e)}
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured channel.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: "HTML" or "Markdown"
        
        Returns:
            True if sent successfully
        """
        data = {
            "chat_id": self.config.channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        result = await self._send_request("sendMessage", data)
        return result.get("ok", False)
    
    async def send_alert(self, 
                        level: AlertLevel, 
                        title: str, 
                        message: str,
                        details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a formatted alert.
        
        Args:
            level: Alert severity level
            title: Alert title
            message: Alert message
            details: Optional key-value details
        """
        # Build formatted message
        text = f"{level.value} <b>{title}</b>\n\n"
        text += f"{message}\n"
        
        if details:
            text += "\n<b>Details:</b>\n"
            for key, value in details.items():
                text += f"• {key}: <code>{value}</code>\n"
        
        text += f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
        
        return await self.send_message(text)
    
    async def send_onchain_report(self, data: Dict[str, Any]) -> bool:
        """
        Send formatted OnChain intelligence report.
        
        Args:
            data: OnChain context data from API
        """
        state = data.get('state', 'UNKNOWN')
        score = data.get('decision_context', {}).get('onchain_score', 'N/A')
        bias = data.get('decision_context', {}).get('bias', 'N/A')
        confidence = data.get('decision_context', {}).get('confidence', 0)
        
        # State emoji
        state_emoji = {
            'ACTIVE': '🟢',
            'DEGRADED': '🟡',
            'BLOCKED': '🔴'
        }.get(state, '⚪')
        
        # Bias emoji
        bias_emoji = {
            'positive': '📈',
            'negative': '📉',
            'neutral': '➡️'
        }.get(bias, '❓')
        
        # Signals
        signals = data.get('signals', {})
        active_signals = [k for k, v in signals.items() if v] if isinstance(signals, dict) else signals.get('active', [])
        
        # Build message
        text = f"""
<b>🔗 OnChain Intelligence Report</b>

{state_emoji} <b>State:</b> {state}
{bias_emoji} <b>Bias:</b> {bias.upper()}
📊 <b>Score:</b> {score}/100
🎯 <b>Confidence:</b> {confidence:.0%}

<b>Active Signals:</b>
"""
        
        if active_signals:
            for signal in active_signals:
                signal_emoji = '🐋' if 'whale' in signal else '💰' if 'money' in signal else '📊'
                text += f"  {signal_emoji} {signal.replace('_', ' ').title()}\n"
        else:
            text += "  None\n"
        
        # Whale metrics
        whale = data.get('metrics', {}).get('whale', {})
        if whale:
            net_flow = whale.get('net_whale_flow', 0)
            flow_emoji = '🟢' if net_flow > 0 else '🔴' if net_flow < 0 else '⚪'
            text += f"""
<b>🐋 Whale Activity:</b>
  {flow_emoji} Net Flow: {net_flow:,.2f} BTC
  📊 Dominance: {whale.get('whale_dominance', 0):.1%}
  🔢 Whale TXs: {whale.get('whale_tx_count', 0)}
"""
        
        # Data quality
        verification = data.get('verification', {})
        text += f"""
<b>📋 Data Quality:</b>
  ✅ Completeness: {verification.get('data_completeness', 1):.0%}
  ⏱️ Data Age: {verification.get('data_age_seconds', 0):.0f}s
  {'✅' if verification.get('invariants_passed') else '❌'} Invariants: {'Passed' if verification.get('invariants_passed') else 'Failed'}
"""
        
        # Usage recommendation
        usage = data.get('usage_policy', {})
        text += f"""
<b>💡 Recommendation:</b>
  {'✅ Use' if usage.get('allowed') else '❌ DO NOT USE'}
  Weight: {usage.get('recommended_weight', 0):.1f}x
"""
        
        text += f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
        
        return await self.send_message(text)
    
    async def send_whale_alert(self, whale_data: Dict[str, Any]) -> bool:
        """
        Send whale activity alert.
        
        Args:
            whale_data: Whale metrics from API
        """
        behavior = whale_data.get('behavior', 'NEUTRAL')
        net_flow = whale_data.get('metrics', {}).get('net_flow_btc', 0)
        
        # Determine alert level
        if abs(net_flow) > 10000:
            level = AlertLevel.CRITICAL
        elif abs(net_flow) > 5000:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO
        
        emoji = '🐋' if behavior == 'ACCUMULATION' else '🦈' if behavior == 'DISTRIBUTION' else '🐟'
        
        text = f"""
{emoji} <b>Whale Alert: {behavior}</b>

{whale_data.get('description', '')}

<b>Metrics:</b>
  💰 Net Flow: {net_flow:+,.2f} BTC
  📊 Volume: {whale_data.get('metrics', {}).get('whale_volume_btc', 0):,.2f} BTC
  🔢 TX Count: {whale_data.get('metrics', {}).get('whale_tx_count', 0)}
  📈 Dominance: {whale_data.get('metrics', {}).get('dominance_ratio', 0):.1%}

<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>
"""
        
        return await self.send_message(text)
    
    async def send_state_change_alert(self, 
                                      old_state: str, 
                                      new_state: str,
                                      reason: Optional[str] = None) -> bool:
        """
        Send alert when system state changes.
        
        Args:
            old_state: Previous state
            new_state: New state
            reason: Reason for change
        """
        # Determine level based on state change
        if new_state == 'BLOCKED':
            level = AlertLevel.CRITICAL
        elif new_state == 'DEGRADED':
            level = AlertLevel.WARNING
        elif old_state in ('BLOCKED', 'DEGRADED') and new_state == 'ACTIVE':
            level = AlertLevel.SUCCESS
        else:
            level = AlertLevel.INFO
        
        state_emoji = {
            'ACTIVE': '🟢',
            'DEGRADED': '🟡', 
            'BLOCKED': '🔴'
        }
        
        text = f"""
{level.value} <b>State Change Alert</b>

{state_emoji.get(old_state, '⚪')} {old_state} → {state_emoji.get(new_state, '⚪')} {new_state}
"""
        
        if reason:
            text += f"\n<b>Reason:</b> {reason}\n"
        
        if new_state == 'BLOCKED':
            text += "\n⚠️ <b>Action Required:</b> OnChain signals should NOT be used for trading decisions!\n"
        
        text += f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
        
        return await self.send_message(text)
    
    async def send_daily_summary(self, stats: Dict[str, Any]) -> bool:
        """
        Send daily summary report.
        
        Args:
            stats: Statistics from /api/v1/onchain/statistics endpoint
        """
        score_stats = stats.get('score_statistics', {})
        bias_dist = stats.get('bias_distribution', {})
        whale_activity = stats.get('whale_activity', {})
        
        text = f"""
📊 <b>Daily OnChain Summary</b>

<b>Score Statistics (24h):</b>
  📈 Average: {score_stats.get('avg_score', 50):.1f}
  ⬆️ Max: {score_stats.get('max_score', 100)}
  ⬇️ Min: {score_stats.get('min_score', 0)}
  🎯 Avg Confidence: {score_stats.get('avg_confidence', 0):.0%}
  📊 Data Points: {score_stats.get('data_points', 0)}

<b>Bias Distribution:</b>
  📈 Positive: {bias_dist.get('positive', 0)}
  ➡️ Neutral: {bias_dist.get('neutral', 0)}
  📉 Negative: {bias_dist.get('negative', 0)}

<b>🐋 Whale Activity:</b>
  💰 Total Volume: {whale_activity.get('total_volume_btc', 0):,.2f} BTC
  🔢 TX Count: {whale_activity.get('total_tx_count', 0)}
  📊 Avg Dominance: {whale_activity.get('avg_dominance', 0):.1%}

<i>Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>
"""
        
        return await self.send_message(text)


# =============================================================================
# Singleton instance
# =============================================================================

_alerter: Optional[TelegramAlerter] = None


def get_telegram_alerter() -> TelegramAlerter:
    """Get or create Telegram alerter singleton."""
    global _alerter
    if _alerter is None:
        _alerter = TelegramAlerter()
    return _alerter


# =============================================================================
# Sync wrappers for non-async code
# =============================================================================

def send_alert_sync(level: AlertLevel, title: str, message: str, 
                   details: Optional[Dict[str, Any]] = None) -> bool:
    """Synchronous wrapper for send_alert."""
    alerter = get_telegram_alerter()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    alerter.send_alert(level, title, message, details)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(
                alerter.send_alert(level, title, message, details)
            )
    except Exception as e:
        logger.error("Failed to send sync alert", error=str(e))
        return False


def send_report_sync(data: Dict[str, Any]) -> bool:
    """Synchronous wrapper for send_onchain_report."""
    alerter = get_telegram_alerter()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    alerter.send_onchain_report(data)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(
                alerter.send_onchain_report(data)
            )
    except Exception as e:
        logger.error("Failed to send sync report", error=str(e))
        return False
