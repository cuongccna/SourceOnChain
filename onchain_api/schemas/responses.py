"""Response schemas for OnChain Intelligence API."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from onchain_api.schemas.models import (
    SignalStatus, BiasType, AssetType, TimeframeType,
    VerificationResult, ComponentScores, SignalBreakdown, MetadataInfo,
    SystemHealth, VerificationTrail, SystemState, QualityMetrics,
    HistorySummary, ErrorDetail, DeprecationWarning
)


class SignalResponse(BaseModel):
    """Primary signal endpoint response."""
    
    # Core signal data (GUARANTEED fields)
    asset: AssetType = Field(..., description="Asset symbol")
    timeframe: TimeframeType = Field(..., description="Signal timeframe")
    timestamp: datetime = Field(..., description="Signal timestamp (UTC)")
    
    onchain_score: Optional[Decimal] = Field(
        None, 
        ge=0, 
        le=100, 
        description="OnChain score (0-100), null when blocked"
    )
    
    confidence: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Signal confidence (0-1)"
    )
    
    bias: BiasType = Field(..., description="Market bias classification")
    status: SignalStatus = Field(..., description="Signal availability status")
    
    # Optional detailed data (present when status != BLOCKED)
    signals: Optional[SignalBreakdown] = Field(
        None, 
        description="Individual signal breakdown"
    )
    
    components: Optional[ComponentScores] = Field(
        None, 
        description="Component score breakdown"
    )
    
    verification: VerificationResult = Field(
        ..., 
        description="Verification and quality metrics"
    )
    
    metadata: MetadataInfo = Field(
        ..., 
        description="Calculation metadata"
    )
    
    # Error information (present when status == BLOCKED)
    block_reason: Optional[str] = Field(
        None, 
        description="Reason for blocking signal"
    )
    
    fallback_available: bool = Field(
        default=False, 
        description="Whether fallback data is available"
    )
    
    retry_after_seconds: Optional[int] = Field(
        None, 
        ge=0, 
        description="Suggested retry interval in seconds"
    )
    
    # API metadata
    warnings: List[DeprecationWarning] = Field(
        default_factory=list, 
        description="API deprecation warnings"
    )

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "asset": "BTC",
                "timeframe": "1d",
                "timestamp": "2024-01-15T12:00:00Z",
                "onchain_score": 72.45,
                "confidence": 0.8234,
                "bias": "positive",
                "status": "OK",
                "signals": {
                    "network_growth_signal": True,
                    "smart_money_accumulation_signal": True,
                    "abnormal_activity_signal": False
                },
                "components": {
                    "network_health": 25.37,
                    "capital_flow": 24.37,
                    "smart_money": 34.27,
                    "risk_penalty": 11.56
                },
                "verification": {
                    "invariants_passed": True,
                    "deterministic": True,
                    "stability_score": 0.89,
                    "data_completeness": 0.96,
                    "last_verification": "2024-01-15T11:58:30Z"
                },
                "metadata": {
                    "calculation_time_ms": 456,
                    "data_age_seconds": 120,
                    "pipeline_lag_blocks": 2
                }
            }
        }


class HealthResponse(BaseModel):
    """Health endpoint response."""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    
    data_pipeline: Dict[str, Any] = Field(
        ..., 
        description="Data pipeline status"
    )
    
    signal_engine: Dict[str, Any] = Field(
        ..., 
        description="Signal engine status"
    )
    
    database: Dict[str, Any] = Field(
        ..., 
        description="Database status"
    )
    
    system_resources: Dict[str, Any] = Field(
        ..., 
        description="System resource utilization"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T12:00:00Z",
                "data_pipeline": {
                    "last_block_height": 825000,
                    "current_block_height": 825002,
                    "pipeline_lag_blocks": 2,
                    "data_freshness_seconds": 180
                },
                "signal_engine": {
                    "status": "operational",
                    "avg_calculation_time_ms": 1234,
                    "success_rate_24h": 0.998
                },
                "database": {
                    "connection_healthy": True,
                    "query_latency_ms": 45
                },
                "system_resources": {
                    "memory_usage_percent": 67,
                    "cpu_usage_percent": 23
                }
            }
        }


class AuditResponse(BaseModel):
    """Audit endpoint response."""
    
    audit_id: str = Field(..., description="Unique audit identifier")
    timestamp: datetime = Field(..., description="Audited timestamp")
    asset: AssetType = Field(..., description="Asset symbol")
    timeframe: TimeframeType = Field(..., description="Signal timeframe")
    
    calculation_result: Dict[str, Any] = Field(
        ..., 
        description="Original calculation result"
    )
    
    verification_trail: VerificationTrail = Field(
        ..., 
        description="Verification and reproducibility data"
    )
    
    system_state: SystemState = Field(
        ..., 
        description="System state at calculation time"
    )
    
    quality_metrics: QualityMetrics = Field(
        ..., 
        description="Quality and verification metrics"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HistoryRecord(BaseModel):
    """Single historical record."""
    
    timestamp: datetime = Field(..., description="Record timestamp")
    
    onchain_score: Optional[Decimal] = Field(
        None, 
        ge=0, 
        le=100, 
        description="OnChain score"
    )
    
    confidence: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Signal confidence"
    )
    
    bias: BiasType = Field(..., description="Market bias")
    status: SignalStatus = Field(..., description="Signal status")
    verification_passed: bool = Field(..., description="Verification status")
    
    block_reason: Optional[str] = Field(
        None, 
        description="Block reason if status == BLOCKED"
    )

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class HistoryResponse(BaseModel):
    """History endpoint response."""
    
    asset: AssetType = Field(..., description="Asset symbol")
    timeframe: TimeframeType = Field(..., description="Signal timeframe")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    
    total_records: int = Field(..., ge=0, description="Total number of records")
    
    records: List[HistoryRecord] = Field(
        ..., 
        description="Historical signal records"
    )
    
    summary: HistorySummary = Field(
        ..., 
        description="Historical data summary"
    )

    class Config:
        schema_extra = {
            "example": {
                "asset": "BTC",
                "timeframe": "1d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-15",
                "total_records": 15,
                "records": [
                    {
                        "timestamp": "2024-01-15T00:00:00Z",
                        "onchain_score": 72.45,
                        "confidence": 0.8234,
                        "bias": "positive",
                        "status": "OK",
                        "verification_passed": True
                    }
                ],
                "summary": {
                    "ok_count": 12,
                    "degraded_count": 2,
                    "blocked_count": 1,
                    "avg_confidence": 0.78,
                    "avg_score": 68.23
                }
            }
        }


class ValidationTestResult(BaseModel):
    """Individual validation test result."""
    
    test_category: str = Field(..., description="Test category")
    passed: int = Field(..., ge=0, description="Tests passed")
    total: int = Field(..., ge=0, description="Total tests")
    details: List[str] = Field(default_factory=list, description="Test details")


class ValidationResponse(BaseModel):
    """Validation endpoint response."""
    
    validation_id: str = Field(..., description="Unique validation identifier")
    timestamp: datetime = Field(..., description="Validation timestamp")
    validation_result: str = Field(..., description="Overall validation result")
    
    signal_preview: Dict[str, Any] = Field(
        ..., 
        description="Preview of signal that would be generated"
    )
    
    verification_results: Dict[str, ValidationTestResult] = Field(
        ..., 
        description="Detailed verification test results"
    )
    
    performance_metrics: Dict[str, Any] = Field(
        ..., 
        description="Performance metrics"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Error response schema."""
    
    error: ErrorDetail = Field(..., description="Error details")
    status: SignalStatus = Field(..., description="Signal status")
    
    fallback_available: bool = Field(
        default=False, 
        description="Whether fallback is available"
    )
    
    retry_after_seconds: Optional[int] = Field(
        None, 
        ge=0, 
        description="Suggested retry interval"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "error": {
                    "code": "SIGNAL_BLOCKED",
                    "message": "Signal blocked due to low confidence",
                    "details": {
                        "confidence": 0.45,
                        "min_required": 0.60,
                        "block_reason": "confidence_below_threshold"
                    },
                    "timestamp": "2024-01-15T12:00:00Z",
                    "request_id": "req_abc123def456"
                },
                "status": "BLOCKED",
                "fallback_available": True,
                "retry_after_seconds": 300
            }
        }


class ValidationRequest(BaseModel):
    """Validation endpoint request schema."""
    
    asset: AssetType = Field(default=AssetType.BTC, description="Asset to validate")
    timeframe: TimeframeType = Field(..., description="Timeframe to validate")
    timestamp: datetime = Field(..., description="Timestamp to validate")
    dry_run: bool = Field(default=True, description="Whether this is a dry run")
    force_recalculation: bool = Field(default=False, description="Force recalculation")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }