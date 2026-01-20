"""Pydantic schemas for OnChain Intelligence Data Product."""

from datetime import datetime
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class DecisionContext(BaseModel):
    """OnChain decision context data."""
    onchain_score: Optional[float] = Field(None, ge=0, le=100, description="OnChain score 0-100, null if blocked")
    bias: Literal["positive", "neutral", "negative"] = Field(..., description="Market bias from on-chain signals")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")


class Signals(BaseModel):
    """Individual OnChain signals."""
    smart_money_accumulation: bool = Field(..., description="Smart money accumulation signal")
    whale_flow_dominant: bool = Field(..., description="Whale flow dominance signal")
    network_growth: bool = Field(..., description="Network growth signal")
    distribution_risk: bool = Field(..., description="Distribution risk signal")


class RiskFlags(BaseModel):
    """Risk flags for data quality."""
    data_lag: bool = Field(..., description="Data lag detected")
    signal_conflict: bool = Field(..., description="Signal conflict detected")
    anomaly_detected: bool = Field(..., description="Anomaly detected")


class Verification(BaseModel):
    """Verification status data."""
    invariants_passed: bool = Field(..., description="All invariant tests passed")
    deterministic: bool = Field(..., description="Calculation is deterministic")
    stability_score: float = Field(..., ge=0, le=1, description="Stability score 0-1")
    data_completeness: float = Field(..., ge=0, le=1, description="Data completeness 0-1")


class UsagePolicy(BaseModel):
    """Usage policy for BotTrading consumption."""
    allowed: bool = Field(..., description="Whether data usage is allowed")
    recommended_weight: float = Field(..., ge=0, le=1, description="Recommended weight 0-1")
    notes: str = Field(..., description="Usage notes")


class OnChainContextResponse(BaseModel):
    """Complete OnChain context response."""
    product: Literal["onchain_intelligence"] = Field(default="onchain_intelligence")
    version: Literal["1.0.0"] = Field(default="1.0.0")
    asset: str = Field(..., description="Asset symbol")
    timeframe: str = Field(..., description="Timeframe")
    timestamp: datetime = Field(..., description="Data timestamp")
    
    state: Literal["ACTIVE", "DEGRADED", "BLOCKED"] = Field(..., description="Data state")
    
    decision_context: DecisionContext = Field(..., description="Decision context data")
    signals: Signals = Field(..., description="Individual signals")
    risk_flags: RiskFlags = Field(..., description="Risk flags")
    verification: Verification = Field(..., description="Verification status")
    usage_policy: UsagePolicy = Field(..., description="Usage policy")


class AuditResponse(BaseModel):
    """Audit response for reproducibility."""
    timestamp: datetime = Field(..., description="Calculation timestamp")
    asset: str = Field(..., description="Asset symbol")
    timeframe: str = Field(..., description="Timeframe")
    input_data_hash: str = Field(..., description="Hash of input data")
    config_hash: str = Field(..., description="Hash of configuration")
    output_snapshot: Dict[str, Any] = Field(..., description="Output data snapshot")