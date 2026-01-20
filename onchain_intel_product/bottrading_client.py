"""
BotTrading client implementation for OnChain Intelligence Data Product.

MANDATORY USAGE RULES:
- If state == BLOCKED → data MUST NOT be used
- On-chain data MUST NOT be treated as trade trigger
- On-chain data provides CONTEXT ONLY  
- Negative bias MUST block long exposure
- Positive bias ONLY allows action if confirmed by other systems
"""

import httpx
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class BotTradingClient:
    """
    Production client for consuming OnChain Intelligence Data Product.
    
    Implements mandatory usage rules and safety checks.
    """
    
    def __init__(self, api_base_url: str, api_key: Optional[str] = None):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        self.logger = logger.bind(component="bottrading_client")
    
    async def get_onchain_context(self, 
                                 asset: str = "BTC",
                                 timeframe: str = "1d",
                                 timestamp: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Get OnChain context with mandatory safety checks.
        
        Returns None if data should not be used.
        """
        
        try:
            params = {
                "asset": asset,
                "timeframe": timeframe
            }
            if timestamp:
                params["timestamp"] = timestamp.isoformat() + "Z"
            
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/api/v1/onchain/context",
                    params=params,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
                context_data = response.json()
                
                # Apply mandatory usage rules
                if not self._validate_usage_rules(context_data):
                    return None
                
                return context_data
                
        except httpx.HTTPError as e:
            self.logger.error("Failed to get OnChain context", error=str(e))
            return None
        except Exception as e:
            self.logger.error("Unexpected error getting OnChain context", error=str(e))
            return None
    
    def _validate_usage_rules(self, context_data: Dict[str, Any]) -> bool:
        """
        Validate mandatory usage rules.
        
        Returns False if data should not be used.
        """
        
        state = context_data.get("state")
        usage_policy = context_data.get("usage_policy", {})
        decision_context = context_data.get("decision_context", {})
        
        # RULE 1: If state == BLOCKED → data MUST NOT be used
        if state == "BLOCKED":
            self.logger.warning("OnChain data BLOCKED - rejecting usage",
                              notes=usage_policy.get("notes", ""))
            return False
        
        # RULE 2: Check usage_policy.allowed
        if not usage_policy.get("allowed", False):
            self.logger.warning("OnChain data usage not allowed - rejecting")
            return False
        
        # Additional safety checks
        verification = context_data.get("verification", {})
        
        # Reject if invariants failed
        if not verification.get("invariants_passed", False):
            self.logger.warning("OnChain data failed invariants - rejecting usage")
            return False
        
        # Reject if not deterministic
        if not verification.get("deterministic", False):
            self.logger.warning("OnChain data not deterministic - rejecting usage")
            return False
        
        self.logger.info("OnChain data passed usage validation",
                        state=state,
                        recommended_weight=usage_policy.get("recommended_weight", 0))
        
        return True
    
    def apply_trading_rules(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply BotTrading rules to OnChain context.
        
        MANDATORY RULES:
        - On-chain data MUST NOT be treated as trade trigger
        - On-chain data provides CONTEXT ONLY
        - Negative bias MUST block long exposure  
        - Positive bias ONLY allows action if confirmed by other systems
        """
        
        decision_context = context_data.get("decision_context", {})
        usage_policy = context_data.get("usage_policy", {})
        
        bias = decision_context.get("bias", "neutral")
        confidence = decision_context.get("confidence", 0.0)
        recommended_weight = usage_policy.get("recommended_weight", 0.0)
        
        trading_guidance = {
            "use_as_context_only": True,  # NEVER as trade trigger
            "allow_long_exposure": bias != "negative",  # Block longs on negative bias
            "allow_short_exposure": True,  # OnChain doesn't restrict shorts
            "context_weight": recommended_weight,
            "requires_confirmation": True,  # ALWAYS require other system confirmation
            "bias_signal": bias,
            "confidence_level": confidence
        }
        
        # Log trading guidance
        self.logger.info("OnChain trading guidance generated",
                        bias=bias,
                        confidence=confidence,
                        allow_long=trading_guidance["allow_long_exposure"],
                        context_weight=trading_guidance["context_weight"])
        
        return trading_guidance


async def example_bottrading_integration():
    """
    Example BotTrading integration showing proper usage.
    """
    
    client = BotTradingClient("http://localhost:8000")
    
    # Get OnChain context
    context = await client.get_onchain_context("BTC", "1d")
    
    if context is None:
        logger.info("No OnChain context available - proceeding without OnChain input")
        return
    
    # Apply trading rules
    trading_guidance = client.apply_trading_rules(context)
    
    # Example BotTrading decision logic
    logger.info("BotTrading decision process starting")
    
    # Get other inputs (technical analysis, sentiment, etc.)
    technical_signal = "bullish"  # Example from technical analysis system
    sentiment_signal = "neutral"  # Example from sentiment analysis
    
    # Combine inputs with OnChain context
    final_decision = make_trading_decision(
        onchain_guidance=trading_guidance,
        technical_signal=technical_signal,
        sentiment_signal=sentiment_signal
    )
    
    logger.info("BotTrading decision completed", decision=final_decision)


def make_trading_decision(onchain_guidance: Dict[str, Any],
                         technical_signal: str,
                         sentiment_signal: str) -> Dict[str, Any]:
    """
    Example trading decision logic incorporating OnChain context.
    
    CRITICAL: OnChain data is CONTEXT ONLY, never the primary trigger.
    """
    
    # Primary decision based on technical and sentiment
    primary_signal = "neutral"
    if technical_signal == "bullish" and sentiment_signal in ["bullish", "neutral"]:
        primary_signal = "bullish"
    elif technical_signal == "bearish" and sentiment_signal in ["bearish", "neutral"]:
        primary_signal = "bearish"
    
    # Apply OnChain context as modifier
    onchain_bias = onchain_guidance.get("bias_signal", "neutral")
    allow_long = onchain_guidance.get("allow_long_exposure", True)
    context_weight = onchain_guidance.get("context_weight", 0.0)
    
    # Final decision logic
    final_signal = "hold"
    confidence = 0.5
    
    if primary_signal == "bullish" and allow_long and onchain_bias != "negative":
        final_signal = "buy"
        # Boost confidence if OnChain supports
        if onchain_bias == "positive":
            confidence += context_weight * 0.2
    elif primary_signal == "bearish":
        final_signal = "sell"
        # Boost confidence if OnChain supports
        if onchain_bias == "negative":
            confidence += context_weight * 0.2
    
    # OnChain negative bias blocks longs regardless of other signals
    if onchain_bias == "negative" and final_signal == "buy":
        final_signal = "hold"
        logger.warning("Long position blocked by negative OnChain bias")
    
    return {
        "signal": final_signal,
        "confidence": min(confidence, 1.0),
        "primary_driver": technical_signal,
        "onchain_modifier": onchain_bias,
        "onchain_weight_applied": context_weight
    }


if __name__ == "__main__":
    asyncio.run(example_bottrading_integration())