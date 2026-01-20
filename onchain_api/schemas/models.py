"""Core data models for OnChain API."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class SignalStatus(str, Enum):
    """Signal availability status."""
    OK = "OK"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class BiasType(str, Enum):
    """Market bias classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class AssetType(str, Enum):
    """Supported asset types."""
    BTC = "BTC"


class TimeframeType(str, Enum):
    """Supported timeframes."""
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class VerificationResult(BaseModel):
    """Signal verification and quality metrics."""
    
    invariants_passed: bool = Field(
        ..., 
        description="Whether all invariant tests passed"
    )
    
    deterministic: bool = Field(
        ..., 
        description="Whether calculation is deterministic"
    )
    
    stability_score: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Signal stability score (0-1)"
    )
    
    data_completeness: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Input data completeness ratio (0-1)"
    )
    
    last_verification: datetime = Field(
        ..., 
        description="Timestamp of last verification run"
    )
    
    verification_tests_passed: int = Field(
        default=0, 
        ge=0, 
        description="Number of verification tests passed"
    )
    
    verification_tests_total: int = Field(
        default=0, 
        ge=0, 
        description="Total number of verification tests"
    )
    
    anomaly_flags: List[str] = Field(
        default_factory=list, 
        description="List of detected anomalies"
    )

    @validator('stability_score', 'data_completeness')
    def validate_decimal_precision(cls, v):
        """Ensure decimal precision is reasonable."""
        return round(v, 4)


class ComponentScores(BaseModel):
    """Component score breakdown."""
    
    network_health: Decimal = Field(
        ..., 
        ge=0, 
        le=30, 
        description="Network health component score (0-30)"
    )
    
    capital_flow: Decimal = Field(
        ..., 
        ge=0, 
        le=30, 
        description="Capital flow component score (0-30)"
    )
    
    smart_money: Decimal = Field(
        ..., 
        ge=0, 
        le=40, 
        description="Smart money component score (0-40)"
    )
    
    risk_penalty: Decimal = Field(
        ..., 
        ge=0, 
        le=20, 
        description="Risk penalty applied (0-20)"
    )

    @validator('network_health', 'capital_flow', 'smart_money', 'risk_penalty')
    def validate_component_precision(cls, v):
        """Ensure component score precision."""
        return round(v, 2)


class SignalBreakdown(BaseModel):
    """Individual signal breakdown."""
    
    network_growth_signal: bool = Field(
        default=False, 
        description="Network growth signal state"
    )
    
    network_congestion_signal: bool = Field(
        default=False, 
        description="Network congestion signal state"
    )
    
    net_utxo_inflow_signal: bool = Field(
        default=False, 
        description="Net UTXO inflow signal state"
    )
    
    whale_flow_dominance_signal: bool = Field(
        default=False, 
        description="Whale flow dominance signal state"
    )
    
    smart_money_accumulation_signal: bool = Field(
        default=False, 
        description="Smart money accumulation signal state"
    )
    
    smart_money_distribution_signal: bool = Field(
        default=False, 
        description="Smart money distribution signal state"
    )
    
    abnormal_activity_signal: bool = Field(
        default=False, 
        description="Abnormal activity signal state"
    )
    
    capital_concentration_signal: bool = Field(
        default=False, 
        description="Capital concentration signal state"
    )


class MetadataInfo(BaseModel):
    """Calculation metadata."""
    
    calculation_time_ms: int = Field(
        ..., 
        ge=0, 
        description="Calculation time in milliseconds"
    )
    
    data_age_seconds: int = Field(
        ..., 
        ge=0, 
        description="Age of input data in seconds"
    )
    
    pipeline_lag_blocks: int = Field(
        ..., 
        ge=0, 
        description="Pipeline lag in blocks"
    )
    
    engine_version: str = Field(
        default="1.0.0", 
        description="Signal engine version"
    )
    
    calculation_node: str = Field(
        default="unknown", 
        description="Node that performed calculation"
    )


class DataPipelineStatus(BaseModel):
    """Data pipeline health status."""
    
    last_block_height: int = Field(
        ..., 
        ge=0, 
        description="Last processed block height"
    )
    
    current_block_height: int = Field(
        ..., 
        ge=0, 
        description="Current blockchain block height"
    )
    
    pipeline_lag_blocks: int = Field(
        ..., 
        ge=0, 
        description="Pipeline lag in blocks"
    )
    
    data_freshness_seconds: int = Field(
        ..., 
        ge=0, 
        description="Data freshness in seconds"
    )
    
    last_successful_calculation: datetime = Field(
        ..., 
        description="Last successful signal calculation"
    )


class SignalEngineStatus(BaseModel):
    """Signal engine health status."""
    
    status: str = Field(
        ..., 
        description="Engine operational status"
    )
    
    avg_calculation_time_ms: int = Field(
        ..., 
        ge=0, 
        description="Average calculation time"
    )
    
    success_rate_24h: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="24-hour success rate"
    )
    
    last_verification_passed: bool = Field(
        ..., 
        description="Last verification test result"
    )
    
    active_kill_switches: List[str] = Field(
        default_factory=list, 
        description="Currently active kill switches"
    )


class DatabaseStatus(BaseModel):
    """Database health status."""
    
    connection_healthy: bool = Field(
        ..., 
        description="Database connection health"
    )
    
    query_latency_ms: int = Field(
        ..., 
        ge=0, 
        description="Average query latency"
    )
    
    connection_pool_usage: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Connection pool usage ratio"
    )


class SystemResources(BaseModel):
    """System resource utilization."""
    
    memory_usage_percent: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Memory usage percentage"
    )
    
    cpu_usage_percent: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="CPU usage percentage"
    )
    
    disk_usage_percent: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Disk usage percentage"
    )


class SystemHealth(BaseModel):
    """Complete system health status."""
    
    status: str = Field(
        ..., 
        description="Overall system status"
    )
    
    timestamp: datetime = Field(
        ..., 
        description="Health check timestamp"
    )
    
    data_pipeline: DataPipelineStatus
    signal_engine: SignalEngineStatus
    database: DatabaseStatus
    system_resources: SystemResources


class VerificationTrail(BaseModel):
    """Audit trail for signal verification."""
    
    input_data_hash: str = Field(
        ..., 
        min_length=64, 
        max_length=64, 
        description="SHA-256 hash of input data"
    )
    
    calculation_hash: str = Field(
        ..., 
        min_length=64, 
        max_length=64, 
        description="SHA-256 hash of calculation result"
    )
    
    config_hash: str = Field(
        ..., 
        min_length=64, 
        max_length=64, 
        description="SHA-256 hash of configuration"
    )
    
    reproducible: bool = Field(
        ..., 
        description="Whether calculation is reproducible"
    )


class SystemState(BaseModel):
    """System state at time of calculation."""
    
    engine_version: str = Field(
        ..., 
        description="Signal engine version"
    )
    
    config_version: str = Field(
        ..., 
        description="Configuration version"
    )
    
    database_version: str = Field(
        ..., 
        description="Database version"
    )
    
    calculation_node: str = Field(
        ..., 
        description="Calculation node identifier"
    )


class QualityMetrics(BaseModel):
    """Signal quality metrics."""
    
    data_completeness: Decimal = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Data completeness ratio"
    )
    
    signal_conflicts: int = Field(
        ..., 
        ge=0, 
        description="Number of conflicting signals"
    )
    
    anomaly_flags: List[str] = Field(
        default_factory=list, 
        description="Detected anomaly flags"
    )
    
    verification_tests_passed: int = Field(
        ..., 
        ge=0, 
        description="Verification tests passed"
    )
    
    verification_tests_total: int = Field(
        ..., 
        ge=0, 
        description="Total verification tests"
    )


class HistorySummary(BaseModel):
    """Historical data summary."""
    
    ok_count: int = Field(
        ..., 
        ge=0, 
        description="Number of OK status records"
    )
    
    degraded_count: int = Field(
        ..., 
        ge=0, 
        description="Number of DEGRADED status records"
    )
    
    blocked_count: int = Field(
        ..., 
        ge=0, 
        description="Number of BLOCKED status records"
    )
    
    avg_confidence: Optional[Decimal] = Field(
        None, 
        ge=0, 
        le=1, 
        description="Average confidence score"
    )
    
    avg_score: Optional[Decimal] = Field(
        None, 
        ge=0, 
        le=100, 
        description="Average OnChain score"
    )


class ErrorDetail(BaseModel):
    """Detailed error information."""
    
    code: str = Field(
        ..., 
        description="Error code"
    )
    
    message: str = Field(
        ..., 
        description="Human-readable error message"
    )
    
    details: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional error details"
    )
    
    timestamp: datetime = Field(
        ..., 
        description="Error timestamp"
    )
    
    request_id: str = Field(
        ..., 
        description="Request identifier for tracking"
    )


class DeprecationWarning(BaseModel):
    """API deprecation warning."""
    
    code: str = Field(
        default="DEPRECATION_WARNING", 
        description="Warning code"
    )
    
    message: str = Field(
        ..., 
        description="Deprecation message"
    )
    
    sunset_date: Optional[str] = Field(
        None, 
        description="Date when feature will be removed"
    )
    
    migration_guide: Optional[str] = Field(
        None, 
        description="URL to migration guide"
    )