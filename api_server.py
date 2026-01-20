"""
OnChain Intelligence API Server for BotTrading

FastAPI server providing on-chain signals for trading decisions.

Architecture:
[ Bitcoin RPC / mempool.space ] ──┐
                                  ├─> On-chain Collector
[ Ethereum RPC / External APIs ] ─┘
                                        ↓
                                Normalize & Verify  
                                        ↓
                                 Signal + Confidence
                                        ↓
                                    BotTrading

Quy tắc sống còn:
1. Không coi RPC / mempool là truth tuyệt đối
2. Phải có completeness score
3. Lag detection
4. BLOCK state
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from btc_collector.core.data_provider import create_data_provider
from btc_collector.models.data_source_config import DataSourceConfig
from btc_collector.core.whale_analyzer import QuickWhaleDetector
from btc_collector.database.persistence import OnChainDatabase, get_database
from btc_collector.core.data_quality import (
    DataQualityChecker, DataState, verify_data,
    COMPLETENESS_THRESHOLD, MAX_DATA_AGE_HOURS
)
from btc_collector.utils.telegram import (
    TelegramAlerter, get_telegram_alerter, AlertLevel
)


# ============================================================
# Pydantic Models
# ============================================================

class DecisionContext(BaseModel):
    onchain_score: Optional[float]
    bias: str  # positive, neutral, negative
    confidence: float


class Signals(BaseModel):
    smart_money_accumulation: bool
    whale_flow_dominant: bool
    network_growth: bool
    distribution_risk: bool


class RiskFlags(BaseModel):
    data_lag: bool
    signal_conflict: bool
    anomaly_detected: bool


class Verification(BaseModel):
    invariants_passed: bool
    deterministic: bool
    stability_score: float
    data_completeness: float
    data_age_seconds: Optional[float] = None
    is_stale: bool = False
    failed_checks: List[str] = []


class UsagePolicy(BaseModel):
    allowed: bool
    recommended_weight: float
    notes: str


class OnChainResponse(BaseModel):
    product: str = "onchain_intelligence"
    version: str = "1.0.0"
    asset: str
    timeframe: str
    timestamp: str
    state: str  # ACTIVE, DEGRADED, BLOCKED
    decision_context: DecisionContext
    signals: Signals
    risk_flags: RiskFlags
    verification: Verification
    usage_policy: UsagePolicy


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    data_source: str
    block_height: int


# ============================================================
# Data Collector
# ============================================================

class OnChainDataCollector:
    """
    Thu thập và xử lý dữ liệu on-chain.
    
    Quy tắc sống còn:
    1. Không coi RPC/mempool là truth tuyệt đối
    2. Phải có completeness score
    3. Lag detection  
    4. BLOCK state
    """
    
    def __init__(self, db: Optional[OnChainDatabase] = None):
        self.config = DataSourceConfig()
        self.provider = create_data_provider(self.config)
        
        # Initialize whale detector with real data
        self.whale_detector = QuickWhaleDetector(self.provider.provider)
        
        # Data quality checker
        self.quality_checker = DataQualityChecker()
        
        # Database persistence
        self.db = db
        
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 60  # 60 seconds cache
        
        # Track last successful collection
        self._last_collection: Optional[datetime] = None
    
    def _is_cache_valid(self) -> bool:
        if self._cache_time is None:
            return False
        return (datetime.utcnow() - self._cache_time).seconds < self._cache_ttl
    
    def collect_all_metrics(self, persist: bool = True) -> dict:
        """Thu thập tất cả metrics."""
        
        # Use cache if valid
        if self._is_cache_valid():
            return self._cache
        
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
        
        # *** REAL WHALE METRICS from Mempool.space API ***
        whale_metrics = self.whale_detector.get_quick_metrics()
        
        self._cache = {
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
            "whale": whale_metrics,
            # Add timestamp for lag detection
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        self._cache_time = datetime.utcnow()
        self._last_collection = datetime.utcnow()
        
        # Persist to database
        if persist and self.db:
            try:
                self.db.save_metrics(self._cache)
            except Exception as e:
                pass  # Don't fail if DB is unavailable
        
        return self._cache
    
    def verify_data_quality(self, metrics: dict, signals: dict) -> dict:
        """
        Verify data quality with completeness, lag detection, anomalies.
        
        Returns verification result with state (ACTIVE/DEGRADED/BLOCKED)
        """
        verification = verify_data(metrics, signals)
        
        return {
            "state": verification.state.value,
            "block_reason": verification.block_reason,
            "invariants_passed": verification.invariants_passed,
            "failed_checks": verification.failed_invariants,
            "quality": verification.quality.to_dict(),
            "confidence_multiplier": verification.confidence_multiplier
        }
    
    def calculate_signals(self, metrics: dict) -> dict:
        """Tính toán signals."""
        blockchain = metrics['blockchain']
        whale = metrics['whale']
        
        net_flow = whale.get('net_whale_flow', 0)
        whale_outflow = whale.get('whale_outflow', 0)
        whale_dominance = whale.get('whale_dominance', 0)
        
        # Smart Money Accumulation: net flow > 0 (more inflow than outflow)
        smart_money_accumulation = net_flow > 0
        
        # Whale Flow Dominant: whale dominance > 30%
        whale_flow_dominant = whale_dominance > 0.30
        
        # Network Growth: avg txs > 2500 per block
        network_growth = blockchain['avg_txs_per_block'] > 2500
        
        # Distribution Risk: significant outflows (net negative flow > 100 BTC)
        distribution_risk = net_flow < 0 and abs(net_flow) > 100
        
        return {
            "smart_money_accumulation": smart_money_accumulation,
            "whale_flow_dominant": whale_flow_dominant,
            "network_growth": network_growth,
            "distribution_risk": distribution_risk
        }
    
    def calculate_score(self, signals: dict) -> tuple:
        """Tính OnChain Score."""
        # Weights: distribution_risk has STRONG negative impact
        weights = {
            "smart_money_accumulation": 35,   # Strong positive
            "whale_flow_dominant": 10,        # Mild positive
            "network_growth": 15,             # Moderate positive
            "distribution_risk": -40          # Strong negative
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
        
        active_signals = sum(1 for v in signals.values() if v)
        conflicting = signals.get('distribution_risk') and signals.get('smart_money_accumulation')
        
        if conflicting:
            confidence = 0.5
        elif active_signals >= 3:
            confidence = 0.85
        elif active_signals >= 2:
            confidence = 0.7
        else:
            confidence = 0.6
        
        return score, bias, confidence


# ============================================================
# FastAPI App
# ============================================================

# Global instances
collector = None
db = None
telegram_alerter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    global collector, db
    print("🚀 Starting OnChain Intelligence API...")
    
    # Initialize database
    try:
        db = get_database()
        print("💾 Database connected")
    except Exception as e:
        print(f"⚠️ Database not available: {e}")
        db = None
    
    # Initialize collector with database
    collector = OnChainDataCollector(db=db)
    print(f"📡 Data Source: {collector.config.data_source}")
    
    # Initialize Telegram alerter
    global telegram_alerter
    telegram_alerter = get_telegram_alerter()
    if telegram_alerter.config.enabled:
        print(f"📱 Telegram alerts enabled")
        # Send startup notification
        await telegram_alerter.send_alert(
            AlertLevel.SUCCESS,
            "OnChain API Started",
            f"Server is running on port {os.getenv('ONCHAIN_API_PORT', '8500')}",
            {"data_source": collector.config.data_source}
        )
    else:
        print("⚠️ Telegram alerts disabled (not configured)")
    
    yield
    
    # Cleanup
    print("👋 Shutting down...")
    if telegram_alerter and telegram_alerter.config.enabled:
        await telegram_alerter.send_alert(
            AlertLevel.WARNING,
            "OnChain API Shutting Down",
            "Server is stopping"
        )
        await telegram_alerter.close()
    if db:
        db.close()


app = FastAPI(
    title="OnChain Intelligence API",
    description="On-chain signals for BotTrading system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Endpoints
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        height = collector.provider.get_block_height()
        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat() + "Z",
            data_source=collector.config.data_source,
            block_height=height
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/v1/onchain/context", response_model=OnChainResponse)
async def get_onchain_context(
    asset: str = Query("BTC", description="Asset symbol"),
    timeframe: str = Query("1h", description="Timeframe")
):
    """
    🎯 Main endpoint for BotTrading
    
    Returns on-chain intelligence context for trading decisions.
    
    Quy tắc sống còn:
    1. Không coi RPC/mempool là truth tuyệt đối
    2. Phải có completeness score  
    3. Lag detection
    4. BLOCK state - Nếu data quality kém, BLOCK signal
    """
    if asset.upper() != "BTC":
        raise HTTPException(status_code=400, detail="Only BTC supported")
    
    try:
        # Collect metrics
        metrics = collector.collect_all_metrics()
        
        # Calculate signals
        signals = collector.calculate_signals(metrics)
        
        # *** CRITICAL: Verify data quality ***
        verification_result = collector.verify_data_quality(metrics, signals)
        quality = verification_result.get('quality', {})
        
        # Get state from verification
        state = verification_result.get('state', 'ACTIVE')
        block_reason = verification_result.get('block_reason')
        invariants_passed = verification_result.get('invariants_passed', True)
        failed_checks = verification_result.get('failed_checks', [])
        
        # Data quality metrics
        completeness = quality.get('completeness_score', 0.95)
        data_age = quality.get('data_age_seconds', 0)
        is_stale = quality.get('is_stale', False)
        
        # Calculate score (set to None if BLOCKED)
        if state == "BLOCKED":
            score = None
            bias = "neutral"
            confidence = 0.0
        else:
            score, bias, confidence = collector.calculate_score(signals)
            # Apply confidence multiplier from data quality
            confidence *= verification_result.get('confidence_multiplier', 1.0)
        
        # Lag detection
        data_lag = is_stale or data_age > (MAX_DATA_AGE_HOURS * 3600)
        
        # Signal conflict detection
        signal_conflict = (
            signals.get('distribution_risk') and signals.get('smart_money_accumulation')
        )
        
        # Persist signals to database
        if db:
            try:
                db.save_signals(signals, score, bias, confidence, state, asset.upper(), timeframe)
            except Exception:
                pass  # Don't fail if DB unavailable
        
        # Build response
        return OnChainResponse(
            asset=asset.upper(),
            timeframe=timeframe,
            timestamp=datetime.utcnow().isoformat() + "Z",
            state=state,
            decision_context=DecisionContext(
                onchain_score=score,
                bias=bias,
                confidence=round(confidence, 2)
            ),
            signals=Signals(**signals),
            risk_flags=RiskFlags(
                data_lag=data_lag,
                signal_conflict=signal_conflict,
                anomaly_detected=len(quality.get('anomalies_detected', [])) > 0
            ),
            verification=Verification(
                invariants_passed=invariants_passed,
                deterministic=not is_stale,
                stability_score=quality.get('overall_quality', 0.9),
                data_completeness=completeness,
                data_age_seconds=data_age,
                is_stale=is_stale,
                failed_checks=failed_checks
            ),
            usage_policy=UsagePolicy(
                allowed=state != "BLOCKED",
                recommended_weight=0.3 if state == "ACTIVE" else (0.15 if state == "DEGRADED" else 0.0),
                notes=f"State: {state}. {block_reason if block_reason else 'Use as context only.' if state != 'BLOCKED' else 'Data blocked.'}"
            )
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/onchain/metrics")
async def get_detailed_metrics():
    """Get detailed on-chain metrics (for debugging)."""
    return collector.collect_all_metrics()


@app.get("/api/v1/onchain/signals")
async def get_signals():
    """Get current signals."""
    metrics = collector.collect_all_metrics()
    signals = collector.calculate_signals(metrics)
    score, bias, confidence = collector.calculate_score(signals)
    
    return {
        "signals": signals,
        "score": score,
        "bias": bias,
        "confidence": confidence
    }


@app.get("/api/v1/onchain/whale")
async def get_whale_metrics():
    """
    Get detailed whale activity metrics.
    
    Returns real-time whale transaction analysis from recent blocks.
    """
    metrics = collector.collect_all_metrics()
    whale = metrics.get('whale', {})
    
    # Determine whale behavior
    net_flow = whale.get('net_whale_flow', 0)
    if net_flow > 100:
        behavior = "ACCUMULATION"
        description = "Whales are accumulating (net inflow)"
    elif net_flow < -100:
        behavior = "DISTRIBUTION"
        description = "Whales are distributing/selling (net outflow)"
    else:
        behavior = "NEUTRAL"
        description = "Balanced whale activity"
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "behavior": behavior,
        "description": description,
        "metrics": {
            "whale_tx_count": whale.get('whale_tx_count', 0),
            "whale_volume_btc": whale.get('whale_volume_btc', 0),
            "inflow_btc": whale.get('whale_inflow', 0),
            "outflow_btc": whale.get('whale_outflow', 0),
            "net_flow_btc": net_flow,
            "dominance_ratio": whale.get('whale_dominance', 0)
        },
        "thresholds": {
            "whale_min_btc": 10,
            "ultra_whale_min_btc": 100,
            "leviathan_min_btc": 1000
        },
        "data_quality": {
            "sampled": whale.get('sampled_txs', 0),
            "estimated": whale.get('estimated', True)
        }
    }


@app.get("/api/v1/onchain/quality")
async def get_data_quality():
    """
    🔍 Data Quality Verification
    
    Quy tắc sống còn:
    1. Không coi RPC/mempool là truth tuyệt đối
    2. completeness score - Đủ dữ liệu không?
    3. lag detection - Dữ liệu có cũ không?
    4. BLOCK state - Có nên dùng data không?
    
    Returns:
    - state: ACTIVE / DEGRADED / BLOCKED
    - completeness_score: 0-1 (>0.8 = good)
    - data_age_seconds: How old is the data
    - is_stale: True if data is too old
    - anomalies: List of detected issues
    """
    metrics = collector.collect_all_metrics()
    signals = collector.calculate_signals(metrics)
    verification = collector.verify_data_quality(metrics, signals)
    
    quality = verification.get('quality', {})
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        
        # State determination
        "state": verification.get('state'),
        "block_reason": verification.get('block_reason'),
        
        # Completeness score (Quy tắc #2)
        "completeness_score": quality.get('completeness_score'),
        "missing_fields": quality.get('missing_fields', []),
        
        # Lag detection (Quy tắc #3)
        "data_age_seconds": quality.get('data_age_seconds'),
        "is_stale": quality.get('is_stale'),
        "max_age_allowed_hours": MAX_DATA_AGE_HOURS,
        
        # Data consistency
        "source_agreement": quality.get('source_agreement', 1.0),
        "conflicting_sources": quality.get('conflicting_sources', []),
        
        # Anomaly detection
        "validity_score": quality.get('validity_score'),
        "anomalies_detected": quality.get('anomalies_detected', []),
        
        # Overall quality
        "overall_quality": quality.get('overall_quality'),
        
        # Invariants check
        "invariants_passed": verification.get('invariants_passed'),
        "failed_checks": verification.get('failed_checks', []),
        
        # Confidence adjustment
        "confidence_multiplier": verification.get('confidence_multiplier'),
        
        # Thresholds
        "thresholds": {
            "completeness": COMPLETENESS_THRESHOLD,
            "max_data_age_hours": MAX_DATA_AGE_HOURS
        }
    }


# ============================================================
# Telegram Reporting Endpoints
# ============================================================

@app.post("/api/v1/telegram/send-report")
async def send_telegram_report():
    """
    📱 Send OnChain report to Telegram channel.
    
    Sends the current on-chain context as a formatted Telegram message.
    """
    if telegram_alerter is None or not telegram_alerter.config.enabled:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    try:
        # Collect current data
        metrics = collector.collect_all_metrics()
        signals = collector.calculate_signals(metrics)
        verification_result = collector.verify_data_quality(metrics, signals)
        
        score, bias, confidence = collector.calculate_score(signals)
        state = verification_result.get('state', 'ACTIVE')
        
        # Build context for report
        report_data = {
            "state": state,
            "decision_context": {
                "onchain_score": score,
                "bias": bias,
                "confidence": confidence * verification_result.get('confidence_multiplier', 1.0)
            },
            "signals": {
                "active": [k for k, v in signals.items() if v]
            },
            "metrics": {
                "whale": metrics.get('whale', {})
            },
            "verification": {
                "data_completeness": verification_result.get('quality', {}).get('completeness_score', 1.0),
                "data_age_seconds": verification_result.get('quality', {}).get('data_age_seconds', 0),
                "invariants_passed": verification_result.get('invariants_passed', True)
            },
            "usage_policy": {
                "allowed": state != "BLOCKED",
                "recommended_weight": 0.3 if state == "ACTIVE" else (0.15 if state == "DEGRADED" else 0.0)
            }
        }
        
        success = await telegram_alerter.send_onchain_report(report_data)
        
        return {
            "success": success,
            "message": "Report sent to Telegram" if success else "Failed to send report",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telegram/send-whale-alert")
async def send_whale_alert():
    """
    🐋 Send whale activity alert to Telegram.
    """
    if telegram_alerter is None or not telegram_alerter.config.enabled:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    try:
        metrics = collector.collect_all_metrics()
        whale = metrics.get('whale', {})
        
        net_flow = whale.get('net_whale_flow', 0)
        if net_flow > 100:
            behavior = "ACCUMULATION"
            description = "Whales are accumulating (net inflow)"
        elif net_flow < -100:
            behavior = "DISTRIBUTION"
            description = "Whales are distributing/selling (net outflow)"
        else:
            behavior = "NEUTRAL"
            description = "Balanced whale activity"
        
        whale_data = {
            "behavior": behavior,
            "description": description,
            "metrics": {
                "net_flow_btc": net_flow,
                "whale_volume_btc": whale.get('whale_volume_btc', 0),
                "whale_tx_count": whale.get('whale_tx_count', 0),
                "dominance_ratio": whale.get('whale_dominance', 0)
            }
        }
        
        success = await telegram_alerter.send_whale_alert(whale_data)
        
        return {
            "success": success,
            "message": "Whale alert sent" if success else "Failed to send",
            "behavior": behavior
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telegram/send-daily-summary")
async def send_daily_summary():
    """
    📊 Send daily summary to Telegram.
    
    Requires database to be configured for statistics.
    """
    if telegram_alerter is None or not telegram_alerter.config.enabled:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        score_stats = db.get_score_statistics(24)
        bias_dist = db.get_bias_distribution(24)
        whale_summary = db.get_whale_activity_summary(24)
        
        stats = {
            "score_statistics": score_stats,
            "bias_distribution": bias_dist,
            "whale_activity": whale_summary
        }
        
        success = await telegram_alerter.send_daily_summary(stats)
        
        return {
            "success": success,
            "message": "Daily summary sent" if success else "Failed to send"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telegram/send-alert")
async def send_custom_alert(
    level: str = Query("INFO", description="Alert level: INFO, SUCCESS, WARNING, ERROR, CRITICAL"),
    title: str = Query(..., description="Alert title"),
    message: str = Query(..., description="Alert message")
):
    """
    📢 Send custom alert to Telegram.
    """
    if telegram_alerter is None or not telegram_alerter.config.enabled:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    try:
        alert_level = AlertLevel[level.upper()]
        success = await telegram_alerter.send_alert(alert_level, title, message)
        
        return {
            "success": success,
            "message": "Alert sent" if success else "Failed to send"
        }
        
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid alert level: {level}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/telegram/status")
async def get_telegram_status():
    """
    📱 Get Telegram alerting status.
    """
    if telegram_alerter is None:
        return {
            "enabled": False,
            "message": "Telegram alerter not initialized"
        }
    
    return {
        "enabled": telegram_alerter.config.enabled,
        "channel_configured": bool(telegram_alerter.config.channel_id),
        "bot_configured": bool(telegram_alerter.config.bot_token)
    }


# ============================================================
# History & Statistics Endpoints (Database Required)
# ============================================================

@app.get("/api/v1/onchain/history")
async def get_history(
    hours: int = Query(24, ge=1, le=168, description="Hours of history (max 168 = 7 days)"),
    asset: str = Query("BTC", description="Asset symbol"),
    timeframe: str = Query("1h", description="Timeframe")
):
    """
    Get historical signals data.
    
    Requires database to be configured.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        history = db.get_signals_history(asset, timeframe, hours)
        return {
            "asset": asset,
            "timeframe": timeframe,
            "hours": hours,
            "count": len(history),
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/onchain/statistics")
async def get_statistics(hours: int = Query(24, ge=1, le=168)):
    """
    Get statistical summary of on-chain signals.
    
    Requires database to be configured.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        score_stats = db.get_score_statistics(hours)
        bias_dist = db.get_bias_distribution(hours)
        whale_summary = db.get_whale_activity_summary(hours)
        
        return {
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "score_statistics": score_stats,
            "bias_distribution": bias_dist,
            "whale_activity": whale_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/onchain/db/status")
async def get_db_status():
    """Get database connection status."""
    if db is None:
        return {
            "connected": False,
            "message": "Database not configured"
        }
    
    try:
        latest = db.get_latest_metrics()
        latest_signal = db.get_latest_signals()
        
        return {
            "connected": True,
            "latest_metrics_at": latest.get('timestamp') if latest else None,
            "latest_signals_at": latest_signal.get('timestamp') if latest_signal else None,
            "tables_initialized": db._initialized
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("""
    ===========================================================
             OnChain Intelligence API for BotTrading           
    ===========================================================
      Architecture:                                            
        [Mempool.space] ─> Collector ─> Normalize ─> Verify    
                                               ↓               
                                      Signal + Confidence       
                                               ↓               
                                           BotTrading           
                                                               
      Quy tắc sống còn:                                        
        1. Không coi RPC/mempool là truth tuyệt đối            
        2. Phải có completeness score                          
        3. Lag detection                                        
        4. BLOCK state                                          
                                                               
      Endpoints:                                               
        GET /health                  - Health check              
        GET /api/v1/onchain/context  - 🎯 Main BotTrading endpoint 
        GET /api/v1/onchain/quality  - 🔍 Data quality verification
        GET /api/v1/onchain/metrics  - Detailed metrics         
        GET /api/v1/onchain/signals  - Current signals
        GET /api/v1/onchain/whale    - Whale activity
        GET /api/v1/onchain/history  - Historical data
        GET /api/v1/onchain/statistics - Score statistics
        GET /api/v1/onchain/db/status - Database status
                                                               
      Docs: http://localhost:{port}/docs                       
    ===========================================================
    """.format(port=os.getenv('ONCHAIN_API_PORT', '8500')))
    
    # Load from environment
    host = os.getenv('ONCHAIN_API_HOST', '0.0.0.0')
    port = int(os.getenv('ONCHAIN_API_PORT', '8500'))
    
    uvicorn.run(app, host=host, port=port)
