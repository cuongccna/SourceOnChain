"""Signal endpoint router."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import structlog

from onchain_api.schemas.responses import SignalResponse, ErrorResponse
from onchain_api.schemas.models import AssetType, TimeframeType, SignalStatus
from onchain_api.services.kill_switch import KillSwitchController, FallbackController
from onchain_api.services.signal_service import SignalService
from onchain_api.app.main import check_rate_limit, get_kill_switch, get_fallback_controller, get_db_session

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/signal", response_model=SignalResponse)
async def get_signal(
    asset: AssetType = Query(default=AssetType.BTC, description="Asset symbol"),
    timeframe: TimeframeType = Query(..., description="Signal timeframe"),
    timestamp: Optional[datetime] = Query(default=None, description="Specific timestamp (ISO 8601 UTC)"),
    include_details: bool = Query(default=False, description="Include detailed signal breakdown"),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    _: str = Depends(check_rate_limit),
    kill_switch: KillSwitchController = Depends(get_kill_switch),
    fallback_controller: FallbackController = Depends(get_fallback_controller),
    db_session: Session = Depends(get_db_session)
):
    """
    Get current on-chain intelligence signal.
    
    This endpoint returns the latest on-chain signal with comprehensive safety checks.
    The signal may be blocked or degraded based on data quality and system health.
    
    **Safety Features:**
    - Automatic blocking when confidence is too low
    - Data quality verification before exposure
    - Kill switch protection against corrupted data
    - Fallback to cached signals when available
    
    **Status Meanings:**
    - `OK`: High-quality signal, safe for automated use
    - `DEGRADED`: Lower-quality signal, use with caution
    - `BLOCKED`: Signal blocked due to safety concerns
    """
    
    request_logger = logger.bind(
        endpoint="get_signal",
        asset=asset.value,
        timeframe=timeframe.value,
        timestamp=timestamp,
        include_details=include_details,
        min_confidence=min_confidence
    )
    
    request_logger.info("Signal request received")
    
    try:
        # Initialize signal service
        signal_service = SignalService(db_session)
        
        # Get raw signal data
        signal_data = await signal_service.get_signal_data(
            asset=asset.value,
            timeframe=timeframe.value,
            timestamp=timestamp
        )
        
        if not signal_data:
            request_logger.warning("No signal data available")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No signal data available for the specified parameters"
            )
        
        # Apply kill switch evaluation
        signal_status, safety_reasons = kill_switch.evaluate_signal_safety(signal_data)
        
        request_logger.info("Kill switch evaluation completed",
                          status=signal_status.value,
                          reasons=safety_reasons)
        
        # Handle different status outcomes
        if signal_status == SignalStatus.BLOCKED:
            # Try fallback signal
            fallback_signal = fallback_controller.get_fallback_signal(asset.value, timeframe.value)
            
            if fallback_signal:
                request_logger.info("Using fallback signal")
                return _create_fallback_response(fallback_signal, safety_reasons)
            else:
                request_logger.warning("No fallback available, returning blocked response")
                return _create_blocked_response(asset, timeframe, safety_reasons, signal_data)
        
        elif signal_status == SignalStatus.DEGRADED:
            # Return degraded signal with warnings
            request_logger.info("Returning degraded signal")
            response = _create_signal_response(signal_data, include_details)
            response.status = SignalStatus.DEGRADED
            response.block_reason = "; ".join(safety_reasons)
            return response
        
        else:  # SignalStatus.OK
            # Cache good signal for potential fallback use
            fallback_controller.cache_signal_for_fallback(asset.value, timeframe.value, signal_data)
            
            request_logger.info("Returning OK signal")
            return _create_signal_response(signal_data, include_details)
    
    except HTTPException:
        raise
    except Exception as e:
        request_logger.error("Signal request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing signal request"
        )


def _create_signal_response(signal_data: dict, include_details: bool) -> SignalResponse:
    """Create SignalResponse from signal data."""
    
    from onchain_api.schemas.models import (
        VerificationResult, ComponentScores, SignalBreakdown, MetadataInfo
    )
    
    # Extract verification data
    verification_data = signal_data.get("verification", {})
    verification = VerificationResult(
        invariants_passed=verification_data.get("invariants_passed", False),
        deterministic=verification_data.get("deterministic", False),
        stability_score=verification_data.get("stability_score", 0.0),
        data_completeness=verification_data.get("data_completeness", 0.0),
        last_verification=verification_data.get("last_verification", datetime.now()),
        verification_tests_passed=verification_data.get("verification_tests_passed", 0),
        verification_tests_total=verification_data.get("verification_tests_total", 0),
        anomaly_flags=verification_data.get("anomaly_flags", [])
    )
    
    # Extract metadata
    metadata_data = signal_data.get("metadata", {})
    metadata = MetadataInfo(
        calculation_time_ms=metadata_data.get("calculation_time_ms", 0),
        data_age_seconds=metadata_data.get("data_age_seconds", 0),
        pipeline_lag_blocks=metadata_data.get("pipeline_lag_blocks", 0),
        engine_version=metadata_data.get("engine_version", "1.0.0"),
        calculation_node=metadata_data.get("calculation_node", "unknown")
    )
    
    # Create response
    response = SignalResponse(
        asset=AssetType(signal_data["asset"]),
        timeframe=TimeframeType(signal_data["timeframe"]),
        timestamp=signal_data["timestamp"],
        onchain_score=signal_data.get("onchain_score"),
        confidence=signal_data["confidence"],
        bias=signal_data["bias"],
        status=SignalStatus.OK,
        verification=verification,
        metadata=metadata
    )
    
    # Add detailed data if requested
    if include_details:
        # Extract component scores
        components_data = signal_data.get("components", {})
        if components_data:
            response.components = ComponentScores(
                network_health=components_data.get("network_health", 0),
                capital_flow=components_data.get("capital_flow", 0),
                smart_money=components_data.get("smart_money", 0),
                risk_penalty=components_data.get("risk_penalty", 0)
            )
        
        # Extract signal breakdown
        signals_data = signal_data.get("signals", {})
        if signals_data:
            response.signals = SignalBreakdown(
                network_growth_signal=signals_data.get("network_growth_signal", False),
                network_congestion_signal=signals_data.get("network_congestion_signal", False),
                net_utxo_inflow_signal=signals_data.get("net_utxo_inflow_signal", False),
                whale_flow_dominance_signal=signals_data.get("whale_flow_dominance_signal", False),
                smart_money_accumulation_signal=signals_data.get("smart_money_accumulation_signal", False),
                smart_money_distribution_signal=signals_data.get("smart_money_distribution_signal", False),
                abnormal_activity_signal=signals_data.get("abnormal_activity_signal", False),
                capital_concentration_signal=signals_data.get("capital_concentration_signal", False)
            )
    
    return response


def _create_blocked_response(asset: AssetType, timeframe: TimeframeType, 
                           reasons: list, signal_data: dict) -> SignalResponse:
    """Create blocked signal response."""
    
    from onchain_api.schemas.models import VerificationResult, MetadataInfo
    
    # Create minimal verification data
    verification = VerificationResult(
        invariants_passed=False,
        deterministic=False,
        stability_score=0.0,
        data_completeness=signal_data.get("verification", {}).get("data_completeness", 0.0),
        last_verification=datetime.now(),
        anomaly_flags=reasons
    )
    
    # Create minimal metadata
    metadata = MetadataInfo(
        calculation_time_ms=0,
        data_age_seconds=signal_data.get("metadata", {}).get("data_age_seconds", 0),
        pipeline_lag_blocks=signal_data.get("metadata", {}).get("pipeline_lag_blocks", 0)
    )
    
    return SignalResponse(
        asset=asset,
        timeframe=timeframe,
        timestamp=signal_data.get("timestamp", datetime.now()),
        onchain_score=None,  # Blocked signals have null score
        confidence=0.0,
        bias="neutral",
        status=SignalStatus.BLOCKED,
        verification=verification,
        metadata=metadata,
        block_reason="; ".join(reasons),
        fallback_available=False,
        retry_after_seconds=300
    )


def _create_fallback_response(fallback_data: dict, block_reasons: list) -> SignalResponse:
    """Create response using fallback signal data."""
    
    response = _create_signal_response(fallback_data, include_details=True)
    response.status = SignalStatus.DEGRADED
    response.block_reason = f"Primary signal blocked: {'; '.join(block_reasons)}"
    response.fallback_available = True
    
    # Add fallback metadata
    response.metadata.data_age_seconds = fallback_data.get("fallback_age_seconds", 0)
    
    return response