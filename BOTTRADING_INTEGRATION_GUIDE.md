# OnChain Intelligence API - Hướng dẫn Sử dụng cho BotTrading

## 📖 Tổng quan

OnChain Intelligence API cung cấp dữ liệu phân tích on-chain Bitcoin cho các hệ thống BotTrading.

---

## 🌐 API Endpoints

### Base URL

```
Production: http://localhost:8000
Development: http://localhost:8000
```

---

## 📊 Nguồn Dữ liệu Đầu vào

### Data Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INPUT DATA SOURCES                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Bitcoin Core RPC (btc_collector)                                    │
│     ├── blocks          → Block metadata, hash, time, difficulty        │
│     ├── transactions    → TX details, inputs, outputs, fees            │
│     └── utxos          → UTXO creation, spending, addresses            │
│                                                                          │
│  2. Normalization Layer (btc_normalization)                             │
│     ├── network_activity_ts    → Active addresses, TX count, volume    │
│     ├── utxo_flow_ts          → UTXO created/spent, net flow           │
│     ├── address_behavior_ts   → New addresses, dormancy, churn         │
│     ├── value_distribution_ts → TX/UTXO percentiles, Gini             │
│     └── large_tx_activity_ts  → Large TX metrics, whale thresholds     │
│                                                                          │
│  3. Whale Detection (whale_detection)                                   │
│     ├── whale_thresholds_cache → P95, P99, P99.9 thresholds            │
│     ├── whale_tx_ts           → Whale TX count, volume, ratio          │
│     ├── whale_utxo_flow_ts    → Whale UTXO creation/spending           │
│     └── whale_behavior_flags_ts → Accumulation, distribution flags     │
│                                                                          │
│  4. Smart Wallet Classification (smart_wallet_classifier)              │
│     ├── wallet_behavior_features → Win rate, PnL, holding time         │
│     └── wallet_classification   → SMART_MONEY, NEUTRAL, DUMB_MONEY     │
│                                                                          │
│  5. Signal Engine (onchain_signal_engine)                               │
│     ├── signal_definitions     → Signal config and thresholds          │
│     ├── signal_calculations    → Computed signal values                │
│     └── onchain_scores        → Final aggregated scores                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Input Tables Summary

| Layer | Table | Description | Update Frequency |
|-------|-------|-------------|------------------|
| Raw | `blocks` | Block headers | Per block (~10 min) |
| Raw | `transactions` | TX data | Per block |
| Raw | `utxos` | UTXO states | Per block |
| Normalized | `network_activity_ts` | Network metrics | 5 minutes |
| Normalized | `utxo_flow_ts` | UTXO flows | 5 minutes |
| Whale | `whale_tx_ts` | Whale activity | 5 minutes |
| Whale | `whale_behavior_flags_ts` | Behavioral flags | 5 minutes |
| Smart | `wallet_classification` | Wallet classes | Hourly |
| Signal | `onchain_scores` | Final scores | 5 minutes |

---

## 🔌 Main Endpoint: GET /api/v1/onchain/context

### Description

Lấy dữ liệu OnChain Intelligence đã được xử lý và đánh giá qua Kill Switch.

### Request

```http
GET /api/v1/onchain/context?asset=BTC&timeframe=1d
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `asset` | string | No | `BTC` | Asset symbol |
| `timeframe` | string | No | `1d` | Timeframe: `1h`, `4h`, `1d` |
| `timestamp` | string | No | now | ISO 8601 UTC timestamp |

### Response

```json
{
  "product": "onchain_intelligence",
  "version": "1.0.0",
  "asset": "BTC",
  "timeframe": "1d",
  "timestamp": "2024-01-15T12:00:00+00:00",
  "state": "ACTIVE",
  "decision_context": {
    "onchain_score": 72.50,
    "bias": "positive",
    "confidence": 0.85
  },
  "signals": {
    "smart_money_accumulation": true,
    "whale_flow_dominant": false,
    "network_growth": true,
    "distribution_risk": false
  },
  "risk_flags": {
    "data_lag": false,
    "signal_conflict": false,
    "anomaly_detected": false
  },
  "verification": {
    "invariants_passed": true,
    "deterministic": true,
    "stability_score": 0.85,
    "data_completeness": 0.95
  },
  "usage_policy": {
    "allowed": true,
    "recommended_weight": 1.0,
    "notes": "Data quality verified. Safe for automated use."
  }
}
```

---

## 📈 Cách Sử dụng trong BotTrading

### Python Client Example

```python
"""Example BotTrading client for OnChain Intelligence API."""

import httpx
from datetime import datetime
from typing import Optional, Dict, Any


class OnChainClient:
    """Client for OnChain Intelligence API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
    
    def get_context(self, 
                   asset: str = "BTC", 
                   timeframe: str = "1d",
                   timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Get OnChain intelligence context.
        
        Args:
            asset: Asset symbol (default: BTC)
            timeframe: Timeframe (1h, 4h, 1d)
            timestamp: Optional ISO 8601 timestamp
            
        Returns:
            OnChain context data
        """
        params = {"asset": asset, "timeframe": timeframe}
        if timestamp:
            params["timestamp"] = timestamp
        
        response = self.client.get(
            f"{self.base_url}/api/v1/onchain/context",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def is_signal_allowed(self, context: Dict[str, Any]) -> bool:
        """Check if signal is allowed for use."""
        return context.get("usage_policy", {}).get("allowed", False)
    
    def get_recommended_weight(self, context: Dict[str, Any]) -> float:
        """Get recommended weight for signal."""
        return context.get("usage_policy", {}).get("recommended_weight", 0.0)
    
    def close(self):
        """Close the client."""
        self.client.close()


# Usage Example
if __name__ == "__main__":
    client = OnChainClient()
    
    try:
        # Get current context
        context = client.get_context(asset="BTC", timeframe="1d")
        
        # Check state
        state = context["state"]
        print(f"State: {state}")
        
        # Check if allowed
        if client.is_signal_allowed(context):
            score = context["decision_context"]["onchain_score"]
            bias = context["decision_context"]["bias"]
            confidence = context["decision_context"]["confidence"]
            weight = client.get_recommended_weight(context)
            
            print(f"OnChain Score: {score}")
            print(f"Bias: {bias}")
            print(f"Confidence: {confidence}")
            print(f"Recommended Weight: {weight}")
            
            # Use in trading decision
            if bias == "positive" and confidence >= 0.7:
                print("Signal: Consider LONG position")
            elif bias == "negative" and confidence >= 0.7:
                print("Signal: Consider SHORT position")
            else:
                print("Signal: Stay NEUTRAL")
        else:
            print("Signal BLOCKED - Do not use for trading")
            print(f"Reason: {context['usage_policy']['notes']}")
            
    finally:
        client.close()
```

### Integration Patterns

#### Pattern 1: Simple Polling

```python
import time

def polling_loop():
    """Simple polling every 5 minutes."""
    client = OnChainClient()
    
    while True:
        context = client.get_context()
        
        if client.is_signal_allowed(context):
            process_signal(context)
        
        time.sleep(300)  # 5 minutes
```

#### Pattern 2: Event-Driven with State Change

```python
def monitor_state_changes():
    """Monitor for state changes."""
    client = OnChainClient()
    last_state = None
    
    while True:
        context = client.get_context()
        current_state = context["state"]
        
        if current_state != last_state:
            print(f"State changed: {last_state} -> {current_state}")
            handle_state_change(current_state, context)
            last_state = current_state
        
        time.sleep(60)  # Check every minute
```

#### Pattern 3: Weighted Decision Making

```python
def make_trading_decision(context: Dict[str, Any], 
                         technical_signal: float,
                         fundamental_signal: float) -> str:
    """
    Combine OnChain signal with other signals.
    
    Args:
        context: OnChain context
        technical_signal: Technical analysis signal (-1 to 1)
        fundamental_signal: Fundamental analysis signal (-1 to 1)
    
    Returns:
        Trading decision
    """
    # Check if OnChain signal is usable
    if not context["usage_policy"]["allowed"]:
        # Fall back to other signals only
        combined = 0.5 * technical_signal + 0.5 * fundamental_signal
    else:
        # Use OnChain signal with recommended weight
        onchain_weight = context["usage_policy"]["recommended_weight"]
        onchain_score = context["decision_context"]["onchain_score"]
        onchain_bias = context["decision_context"]["bias"]
        
        # Convert bias to signal (-1, 0, 1)
        if onchain_bias == "positive":
            onchain_signal = onchain_score / 100  # 0 to 1
        elif onchain_bias == "negative":
            onchain_signal = -onchain_score / 100  # -1 to 0
        else:
            onchain_signal = 0
        
        # Weighted combination
        remaining_weight = 1 - onchain_weight
        combined = (
            onchain_weight * onchain_signal +
            remaining_weight * 0.5 * technical_signal +
            remaining_weight * 0.5 * fundamental_signal
        )
    
    # Make decision
    if combined > 0.3:
        return "LONG"
    elif combined < -0.3:
        return "SHORT"
    else:
        return "NEUTRAL"
```

---

## 🚦 State Machine

### States

| State | Description | `allowed` | `recommended_weight` |
|-------|-------------|-----------|---------------------|
| `ACTIVE` | Data quality verified | `true` | `1.0` |
| `DEGRADED` | Reduced quality | `true` | `0.3` |
| `BLOCKED` | Do not use | `false` | `0.0` |

### BLOCKED Conditions (Hard Rules)

- `invariants_passed == false`
- `data_lag == true`
- `confidence < 0.60`
- `deterministic == false`

### DEGRADED Conditions

- `stability_score < 0.70`
- `data_completeness < 0.80`
- `signal_conflict == true`

---

## 🔍 Additional Endpoints

### Health Check

```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "product": "onchain_intelligence",
  "version": "1.0.0",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

### Audit Trail

```http
GET /api/v1/onchain/audit/{timestamp}?asset=BTC&timeframe=1d
```

Response:
```json
{
  "timestamp": "2024-01-15T12:00:00+00:00",
  "asset": "BTC",
  "timeframe": "1d",
  "input_data_hash": "abc123...",
  "config_hash": "def456...",
  "output_snapshot": {
    "onchain_score": 72.50,
    "confidence": 0.85,
    "bias": "positive"
  }
}
```

---

## ⚙️ Scheduler Setup

### Chạy Pipeline Scheduler

```bash
# Development
cd onchain_intel_product
python scheduler.py

# Production with PM2
pm2 start scheduler.py --interpreter python3 --name "onchain-scheduler"
```

### Environment Variables

```bash
# Database
ONCHAIN_DATABASE_URL=postgresql://user:pass@localhost:5432/bitcoin_onchain_signals

# Scheduler
ONCHAIN_SCHEDULER_INTERVAL=5  # minutes
ONCHAIN_TIMEFRAMES=1h,4h,1d

# Pipeline toggles
ONCHAIN_ENABLE_COLLECTION=true
ONCHAIN_ENABLE_NORMALIZATION=true
ONCHAIN_ENABLE_WHALE_DETECTION=true
ONCHAIN_ENABLE_SMART_WALLET=true
ONCHAIN_ENABLE_SIGNAL_ENGINE=true
```

---

## 🧪 Testing

### Run Tests

```bash
cd SourceOnChain
pytest tests/ -v

# With coverage
pytest tests/ --cov=onchain_intel_product --cov-report=html
```

### Test Files

- `tests/test_kill_switch.py` - Kill switch logic tests
- `tests/test_api_integration.py` - API endpoint tests
- `tests/test_data_quality.py` - Data validation tests

---

## 📋 Best Practices for BotTrading Integration

### DO ✅

1. **Always check `usage_policy.allowed`** before using the signal
2. **Use `recommended_weight`** to adjust signal strength
3. **Monitor `state` changes** and log them
4. **Implement fallback logic** when state is BLOCKED
5. **Cache responses** to handle API downtime
6. **Set reasonable timeouts** (30s recommended)

### DON'T ❌

1. **Don't ignore BLOCKED state** - This is a safety mechanism
2. **Don't hardcode weights** - Use `recommended_weight` instead
3. **Don't poll too frequently** - 5 minutes is the update interval
4. **Don't rely solely on OnChain signals** - Combine with other indicators
5. **Don't skip health checks** - Monitor `/health` endpoint

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| State always BLOCKED | Low confidence | Check data pipeline health |
| Empty signals | No data in database | Run scheduler first |
| Connection timeout | API not running | Start uvicorn server |
| 500 errors | Database connection failed | Check DATABASE_URL |

### Health Check Flow

```python
def check_system_health():
    """Check OnChain system health."""
    client = OnChainClient()
    
    # 1. Check API health
    health = client.client.get(f"{client.base_url}/health").json()
    if health["status"] != "healthy":
        raise Exception("API unhealthy")
    
    # 2. Check context availability
    context = client.get_context()
    if context["state"] == "BLOCKED":
        print("WARNING: Signal is blocked")
        print(f"Reason: {context['usage_policy']['notes']}")
    
    # 3. Check data freshness
    timestamp = context["timestamp"]
    # Parse and check age...
    
    client.close()
```

---

*Last Updated: January 17, 2026*
