"""
BotTrading Integration Example for OnChain Intelligence API

This module demonstrates how to safely consume OnChain intelligence signals
in a BotTrading system with proper safety checks and risk management.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import httpx
import structlog

logger = structlog.get_logger(__name__)


class SignalStatus(str, Enum):
    """Signal status from OnChain API."""
    OK = "OK"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class TradingDecision(str, Enum):
    """Trading decision outcomes."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_ACTION = "NO_ACTION"


@dataclass
class OnChainSignalInput:
    """OnChain signal input for trading decision."""
    
    # Core signal data
    asset: str
    timeframe: str
    timestamp: datetime
    onchain_score: Optional[float]
    confidence: float
    bias: str
    status: SignalStatus
    
    # Quality metrics
    data_completeness: float
    verification_passed: bool
    active_signals: int
    conflicting_signals: int
    
    # Metadata
    data_age_seconds: int
    calculation_time_ms: int
    fallback_mode: bool = False
    
    # Risk assessment
    usable: bool = False
    weight: float = 0.0
    risk_flags: List[str] = None
    
    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []


@dataclass
class TradingSignalWeights:
    """Weights for different signal sources."""
    
    onchain_max_weight: float = 0.25  # Maximum 25% weight for onchain signals
    technical_analysis_weight: float = 0.40
    market_sentiment_weight: float = 0.20
    risk_management_weight: float = 0.15
    
    # Quality-based weight adjustments
    high_confidence_bonus: float = 0.05  # Bonus for high confidence signals
    degraded_penalty: float = 0.10  # Penalty for degraded signals
    fallback_penalty: float = 0.15  # Penalty for fallback signals


class OnChainAPIClient:
    """Safe client for OnChain Intelligence API."""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.logger = logger.bind(component="onchain_api_client")
        
        # Request session with retry logic
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"X-API-Key": api_key},
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    async def get_signal(self, asset: str = "BTC", timeframe: str = "1d",
                        include_details: bool = True,
                        min_confidence: Optional[float] = None) -> Optional[OnChainSignalInput]:
        """
        Get OnChain signal with comprehensive safety checks.
        
        Args:
            asset: Asset symbol
            timeframe: Signal timeframe
            include_details: Include detailed signal breakdown
            min_confidence: Minimum confidence threshold
            
        Returns:
            OnChainSignalInput or None if request fails
        """
        
        self.logger.info("Requesting OnChain signal",
                        asset=asset,
                        timeframe=timeframe,
                        min_confidence=min_confidence)
        
        try:
            # Build request parameters
            params = {
                "asset": asset,
                "timeframe": timeframe,
                "include_details": include_details
            }
            
            if min_confidence is not None:
                params["min_confidence"] = min_confidence
            
            # Make API request with retry logic
            response = await self._make_request_with_retry(
                "GET", 
                f"{self.base_url}/api/v1/onchain/signal",
                params=params
            )
            
            if response is None:
                return None
            
            # Parse and validate response
            signal_input = self._parse_signal_response(response)
            
            # Apply safety checks
            signal_input = self._apply_safety_checks(signal_input)
            
            self.logger.info("OnChain signal received",
                           status=signal_input.status.value,
                           confidence=signal_input.confidence,
                           usable=signal_input.usable,
                           weight=signal_input.weight)
            
            return signal_input
            
        except Exception as e:
            self.logger.error("Failed to get OnChain signal", error=str(e))
            return None
    
    async def _make_request_with_retry(self, method: str, url: str, 
                                     params: Optional[Dict] = None,
                                     max_retries: int = 3) -> Optional[Dict]:
        """Make HTTP request with retry logic."""
        
        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 202:
                    # Degraded signal - still usable
                    return response.json()
                elif response.status_code == 503:
                    # Service unavailable - blocked signal
                    data = response.json()
                    self.logger.warning("Signal blocked by API", reason=data.get("error", {}).get("message"))
                    return data
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.warning("Rate limited", retry_after=retry_after)
                    await asyncio.sleep(min(retry_after, 300))  # Max 5 minute wait
                    continue
                else:
                    self.logger.warning("API request failed", 
                                      status_code=response.status_code,
                                      response=response.text)
                    
            except httpx.TimeoutException:
                self.logger.warning("API request timeout", attempt=attempt + 1)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
            except Exception as e:
                self.logger.error("API request error", error=str(e), attempt=attempt + 1)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        return None
    
    def _parse_signal_response(self, response_data: Dict) -> OnChainSignalInput:
        """Parse API response into OnChainSignalInput."""
        
        # Handle error responses
        if "error" in response_data:
            return OnChainSignalInput(
                asset=response_data.get("asset", "BTC"),
                timeframe=response_data.get("timeframe", "1d"),
                timestamp=datetime.now(),
                onchain_score=None,
                confidence=0.0,
                bias="neutral",
                status=SignalStatus.BLOCKED,
                data_completeness=0.0,
                verification_passed=False,
                active_signals=0,
                conflicting_signals=0,
                data_age_seconds=0,
                calculation_time_ms=0,
                risk_flags=["api_error"]
            )
        
        # Parse successful response
        verification = response_data.get("verification", {})
        metadata = response_data.get("metadata", {})
        
        return OnChainSignalInput(
            asset=response_data["asset"],
            timeframe=response_data["timeframe"],
            timestamp=datetime.fromisoformat(response_data["timestamp"].replace("Z", "+00:00")),
            onchain_score=response_data.get("onchain_score"),
            confidence=response_data["confidence"],
            bias=response_data["bias"],
            status=SignalStatus(response_data["status"]),
            data_completeness=verification.get("data_completeness", 0.0),
            verification_passed=verification.get("invariants_passed", False),
            active_signals=len([s for s in response_data.get("signals", {}).values() if s]),
            conflicting_signals=0,  # Would be calculated from signal analysis
            data_age_seconds=metadata.get("data_age_seconds", 0),
            calculation_time_ms=metadata.get("calculation_time_ms", 0),
            fallback_mode=response_data.get("fallback_mode", False)
        )
    
    def _apply_safety_checks(self, signal: OnChainSignalInput) -> OnChainSignalInput:
        """Apply comprehensive safety checks to signal."""
        
        risk_flags = []
        usable = True
        base_weight = 0.25  # 25% base weight for onchain signals
        
        # 1. Status checks
        if signal.status == SignalStatus.BLOCKED:
            usable = False
            risk_flags.append("signal_blocked")
            base_weight = 0.0
        elif signal.status == SignalStatus.DEGRADED:
            risk_flags.append("signal_degraded")
            base_weight *= 0.7  # 30% penalty for degraded signals
        
        # 2. Confidence checks
        if signal.confidence < 0.3:
            usable = False
            risk_flags.append("confidence_too_low")
        elif signal.confidence < 0.6:
            risk_flags.append("confidence_low")
            base_weight *= 0.8  # 20% penalty for low confidence
        elif signal.confidence > 0.8:
            base_weight *= 1.1  # 10% bonus for high confidence
        
        # 3. Data quality checks
        if signal.data_completeness < 0.5:
            usable = False
            risk_flags.append("data_completeness_critical")
        elif signal.data_completeness < 0.8:
            risk_flags.append("data_completeness_low")
            base_weight *= 0.9  # 10% penalty for low data completeness
        
        # 4. Verification checks
        if not signal.verification_passed:
            usable = False
            risk_flags.append("verification_failed")
        
        # 5. Data freshness checks
        if signal.data_age_seconds > 3600:  # 1 hour
            risk_flags.append("data_stale")
            base_weight *= 0.8  # 20% penalty for stale data
        elif signal.data_age_seconds > 7200:  # 2 hours
            usable = False
            risk_flags.append("data_too_stale")
        
        # 6. Fallback mode checks
        if signal.fallback_mode:
            risk_flags.append("fallback_mode")
            base_weight *= 0.6  # 40% penalty for fallback signals
        
        # 7. Signal conflict checks
        if signal.conflicting_signals > 2:
            risk_flags.append("high_signal_conflicts")
            base_weight *= 0.7  # 30% penalty for conflicting signals
        
        # 8. Missing score check
        if signal.onchain_score is None:
            usable = False
            risk_flags.append("missing_score")
        
        # Final weight calculation
        final_weight = min(base_weight, 0.25) if usable else 0.0
        
        # Update signal with safety assessment
        signal.usable = usable
        signal.weight = final_weight
        signal.risk_flags = risk_flags
        
        return signal
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class BotTradingDecisionEngine:
    """Main trading decision engine that safely consumes OnChain signals."""
    
    def __init__(self, onchain_client: OnChainAPIClient, 
                 signal_weights: TradingSignalWeights):
        self.onchain_client = onchain_client
        self.signal_weights = signal_weights
        self.logger = logger.bind(component="trading_decision_engine")
        
        # Signal history for trend analysis
        self.signal_history: List[OnChainSignalInput] = []
        self.max_history = 100
    
    async def make_trading_decision(self, asset: str = "BTC") -> Tuple[TradingDecision, Dict[str, Any]]:
        """
        Make trading decision using multiple signal sources.
        
        CRITICAL: OnChain signals are NEVER the sole decision factor.
        
        Args:
            asset: Asset to analyze
            
        Returns:
            Tuple of (decision, decision_metadata)
        """
        
        self.logger.info("Making trading decision", asset=asset)
        
        decision_metadata = {
            "timestamp": datetime.now(),
            "asset": asset,
            "signal_sources": {},
            "final_score": 0.0,
            "confidence": 0.0,
            "risk_flags": [],
            "decision_factors": []
        }
        
        try:
            # 1. Get OnChain signal (ONE input among many)
            onchain_signal = await self._get_onchain_input(asset)
            decision_metadata["signal_sources"]["onchain"] = self._serialize_signal(onchain_signal)
            
            # 2. Get other signal sources (REQUIRED - never rely on onchain alone)
            technical_signal = await self._get_technical_analysis_input(asset)
            decision_metadata["signal_sources"]["technical"] = technical_signal
            
            sentiment_signal = await self._get_market_sentiment_input(asset)
            decision_metadata["signal_sources"]["sentiment"] = sentiment_signal
            
            risk_signal = await self._get_risk_management_input(asset)
            decision_metadata["signal_sources"]["risk"] = risk_signal
            
            # 3. Combine all signals with proper weighting
            combined_score, combined_confidence = self._combine_signals(
                onchain_signal, technical_signal, sentiment_signal, risk_signal
            )
            
            decision_metadata["final_score"] = combined_score
            decision_metadata["confidence"] = combined_confidence
            
            # 4. Make final decision with safety checks
            decision = self._make_final_decision(combined_score, combined_confidence, decision_metadata)
            
            # 5. Update signal history
            if onchain_signal:
                self._update_signal_history(onchain_signal)
            
            self.logger.info("Trading decision made",
                           decision=decision.value,
                           final_score=combined_score,
                           confidence=combined_confidence,
                           onchain_usable=onchain_signal.usable if onchain_signal else False)
            
            return decision, decision_metadata
            
        except Exception as e:
            self.logger.error("Trading decision failed", error=str(e))
            decision_metadata["error"] = str(e)
            return TradingDecision.NO_ACTION, decision_metadata
    
    async def _get_onchain_input(self, asset: str) -> Optional[OnChainSignalInput]:
        """Get OnChain signal input with safety checks."""
        
        try:
            # Request signal with minimum confidence threshold
            signal = await self.onchain_client.get_signal(
                asset=asset,
                timeframe="1d",
                include_details=True,
                min_confidence=0.6  # Require at least 60% confidence
            )
            
            if signal and signal.usable:
                self.logger.debug("OnChain signal usable",
                                confidence=signal.confidence,
                                weight=signal.weight,
                                risk_flags=signal.risk_flags)
                return signal
            else:
                self.logger.warning("OnChain signal not usable",
                                  status=signal.status.value if signal else "unavailable",
                                  risk_flags=signal.risk_flags if signal else [])
                return signal  # Return even if not usable for logging
                
        except Exception as e:
            self.logger.error("Failed to get OnChain input", error=str(e))
            return None
    
    async def _get_technical_analysis_input(self, asset: str) -> Dict[str, Any]:
        """Get technical analysis input (placeholder)."""
        
        # Placeholder for technical analysis
        # In real implementation, this would call technical analysis services
        return {
            "score": 0.65,
            "confidence": 0.8,
            "indicators": {
                "rsi": 45,
                "macd": "bullish",
                "moving_averages": "neutral"
            },
            "usable": True,
            "weight": self.signal_weights.technical_analysis_weight
        }
    
    async def _get_market_sentiment_input(self, asset: str) -> Dict[str, Any]:
        """Get market sentiment input (placeholder)."""
        
        # Placeholder for sentiment analysis
        return {
            "score": 0.55,
            "confidence": 0.7,
            "sources": {
                "social_media": 0.6,
                "news_sentiment": 0.5,
                "options_flow": 0.55
            },
            "usable": True,
            "weight": self.signal_weights.market_sentiment_weight
        }
    
    async def _get_risk_management_input(self, asset: str) -> Dict[str, Any]:
        """Get risk management input (placeholder)."""
        
        # Placeholder for risk management
        return {
            "score": 0.7,  # Higher score = lower risk
            "confidence": 0.9,
            "factors": {
                "portfolio_exposure": 0.3,
                "market_volatility": 0.6,
                "correlation_risk": 0.8
            },
            "usable": True,
            "weight": self.signal_weights.risk_management_weight
        }
    
    def _combine_signals(self, onchain_signal: Optional[OnChainSignalInput],
                        technical_signal: Dict[str, Any],
                        sentiment_signal: Dict[str, Any],
                        risk_signal: Dict[str, Any]) -> Tuple[float, float]:
        """Combine all signal sources with proper weighting."""
        
        weighted_scores = []
        total_weight = 0.0
        confidence_factors = []
        
        # OnChain signal (maximum 25% weight)
        if onchain_signal and onchain_signal.usable and onchain_signal.onchain_score is not None:
            # Normalize OnChain score to 0-1 range
            normalized_score = onchain_signal.onchain_score / 100.0
            
            # Apply bias adjustment
            if onchain_signal.bias == "positive":
                bias_adjustment = 0.1
            elif onchain_signal.bias == "negative":
                bias_adjustment = -0.1
            else:
                bias_adjustment = 0.0
            
            adjusted_score = max(0.0, min(1.0, normalized_score + bias_adjustment))
            
            weighted_scores.append(adjusted_score * onchain_signal.weight)
            total_weight += onchain_signal.weight
            confidence_factors.append(onchain_signal.confidence * onchain_signal.weight)
        
        # Technical analysis signal
        if technical_signal["usable"]:
            weighted_scores.append(technical_signal["score"] * technical_signal["weight"])
            total_weight += technical_signal["weight"]
            confidence_factors.append(technical_signal["confidence"] * technical_signal["weight"])
        
        # Market sentiment signal
        if sentiment_signal["usable"]:
            weighted_scores.append(sentiment_signal["score"] * sentiment_signal["weight"])
            total_weight += sentiment_signal["weight"]
            confidence_factors.append(sentiment_signal["confidence"] * sentiment_signal["weight"])
        
        # Risk management signal
        if risk_signal["usable"]:
            weighted_scores.append(risk_signal["score"] * risk_signal["weight"])
            total_weight += risk_signal["weight"]
            confidence_factors.append(risk_signal["confidence"] * risk_signal["weight"])
        
        # Calculate combined score and confidence
        if total_weight > 0:
            combined_score = sum(weighted_scores) / total_weight
            combined_confidence = sum(confidence_factors) / total_weight
        else:
            combined_score = 0.5  # Neutral
            combined_confidence = 0.0
        
        return combined_score, combined_confidence
    
    def _make_final_decision(self, combined_score: float, combined_confidence: float,
                           metadata: Dict[str, Any]) -> TradingDecision:
        """Make final trading decision with safety checks."""
        
        # Minimum confidence required for any action
        MIN_CONFIDENCE = 0.6
        
        # Decision thresholds
        BUY_THRESHOLD = 0.65
        SELL_THRESHOLD = 0.35
        
        decision_factors = []
        
        # Check minimum confidence
        if combined_confidence < MIN_CONFIDENCE:
            decision_factors.append(f"confidence_too_low_{combined_confidence:.3f}")
            metadata["decision_factors"] = decision_factors
            return TradingDecision.NO_ACTION
        
        # Check for critical risk flags
        onchain_data = metadata["signal_sources"].get("onchain", {})
        if onchain_data.get("risk_flags"):
            critical_flags = ["signal_blocked", "verification_failed", "data_too_stale"]
            if any(flag in onchain_data["risk_flags"] for flag in critical_flags):
                decision_factors.append("critical_onchain_risk_flags")
                metadata["decision_factors"] = decision_factors
                return TradingDecision.NO_ACTION
        
        # Make decision based on combined score
        if combined_score >= BUY_THRESHOLD:
            decision_factors.append(f"combined_score_bullish_{combined_score:.3f}")
            decision = TradingDecision.BUY
        elif combined_score <= SELL_THRESHOLD:
            decision_factors.append(f"combined_score_bearish_{combined_score:.3f}")
            decision = TradingDecision.SELL
        else:
            decision_factors.append(f"combined_score_neutral_{combined_score:.3f}")
            decision = TradingDecision.HOLD
        
        metadata["decision_factors"] = decision_factors
        return decision
    
    def _serialize_signal(self, signal: Optional[OnChainSignalInput]) -> Dict[str, Any]:
        """Serialize OnChain signal for metadata."""
        
        if not signal:
            return {"available": False}
        
        return {
            "available": True,
            "status": signal.status.value,
            "confidence": signal.confidence,
            "onchain_score": signal.onchain_score,
            "bias": signal.bias,
            "usable": signal.usable,
            "weight": signal.weight,
            "risk_flags": signal.risk_flags,
            "data_completeness": signal.data_completeness,
            "data_age_seconds": signal.data_age_seconds,
            "fallback_mode": signal.fallback_mode
        }
    
    def _update_signal_history(self, signal: OnChainSignalInput):
        """Update signal history for trend analysis."""
        
        self.signal_history.append(signal)
        
        # Keep only recent history
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]
    
    def get_signal_trend_analysis(self, lookback_periods: int = 10) -> Dict[str, Any]:
        """Analyze recent signal trends."""
        
        if len(self.signal_history) < lookback_periods:
            return {"insufficient_data": True}
        
        recent_signals = self.signal_history[-lookback_periods:]
        
        # Calculate trend metrics
        usable_signals = [s for s in recent_signals if s.usable]
        avg_confidence = sum(s.confidence for s in usable_signals) / len(usable_signals) if usable_signals else 0
        avg_score = sum(s.onchain_score for s in usable_signals if s.onchain_score) / len([s for s in usable_signals if s.onchain_score]) if usable_signals else 0
        
        # Count status distribution
        status_counts = {}
        for signal in recent_signals:
            status_counts[signal.status.value] = status_counts.get(signal.status.value, 0) + 1
        
        return {
            "lookback_periods": lookback_periods,
            "total_signals": len(recent_signals),
            "usable_signals": len(usable_signals),
            "avg_confidence": avg_confidence,
            "avg_score": avg_score,
            "status_distribution": status_counts,
            "reliability_score": len(usable_signals) / len(recent_signals)
        }


# Example usage and testing
async def main():
    """Example usage of BotTrading integration."""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize OnChain API client
    onchain_client = OnChainAPIClient(
        base_url="http://localhost:8000",
        api_key="your-api-key-here"
    )
    
    # Initialize trading decision engine
    signal_weights = TradingSignalWeights()
    trading_engine = BotTradingDecisionEngine(onchain_client, signal_weights)
    
    try:
        # Make trading decision
        decision, metadata = await trading_engine.make_trading_decision("BTC")
        
        print(f"Trading Decision: {decision.value}")
        print(f"Final Score: {metadata['final_score']:.3f}")
        print(f"Confidence: {metadata['confidence']:.3f}")
        print(f"OnChain Signal Usable: {metadata['signal_sources']['onchain'].get('usable', False)}")
        
        # Get trend analysis
        trend_analysis = trading_engine.get_signal_trend_analysis()
        print(f"Signal Reliability: {trend_analysis.get('reliability_score', 0):.3f}")
        
    finally:
        await onchain_client.close()


if __name__ == "__main__":
    asyncio.run(main())