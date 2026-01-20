# Architecture Decision: OnChain API Modules

## Context

Dự án có 2 FastAPI applications với chức năng tương tự:
- `onchain_api/` 
- `onchain_intel_product/`

## Decision

**Giữ cả hai modules với mục đích rõ ràng khác nhau.**

---

## Module Definitions

### 1. `onchain_api/` - INTERNAL API

**Mục đích:** API nội bộ cho hệ thống internal, monitoring, và development.

**Đặc điểm:**
- Full-featured với nhiều endpoints
- SQLAlchemy ORM cho flexibility
- Prometheus metrics integration
- Rate limiting per client
- CORS configuration
- Detailed logging với request tracing
- Multiple routers (signal, health, audit, history, validation)

**Endpoints:**
```
GET /api/v1/onchain/signal     - Raw signal data
GET /api/v1/onchain/health     - Health check với details
GET /api/v1/onchain/audit/{ts} - Audit trail
GET /api/v1/onchain/history    - Historical signals
GET /api/v1/onchain/validate   - Validation checks
```

**Use Cases:**
- Internal dashboards
- Monitoring systems
- Development & debugging
- Data exploration
- Signal validation

---

### 2. `onchain_intel_product/` - EXTERNAL PRODUCT API

**Mục đích:** Production API đơn giản hóa cho BotTrading systems.

**Đặc điểm:**
- Simplified single-file implementation
- psycopg2 raw queries (performance optimized)
- Minimal dependencies
- Pre-aggregated "context" response
- Built-in usage policy cho consumers
- Standalone deployment (có thể deploy riêng biệt)

**Endpoints:**
```
GET /api/v1/onchain/context    - Aggregated context cho decision making
GET /api/v1/onchain/audit/{ts} - Audit trail (simplified)
GET /health                    - Basic health check
```

**Use Cases:**
- BotTrading integration
- External consumer APIs
- Production trading systems
- Third-party integrations

---

## Response Comparison

### `onchain_api/signal`:
```json
{
  "asset": "BTC",
  "timeframe": "1d",
  "onchain_score": 65.5,
  "confidence": 0.85,
  "bias": "positive",
  "status": "OK",
  "signals": { ... detailed signals ... },
  "metadata": { ... internal details ... }
}
```

### `onchain_intel_product/context`:
```json
{
  "product": "onchain_intelligence",
  "version": "1.0.0",
  "state": "ACTIVE",
  "decision_context": {
    "onchain_score": 65.5,
    "bias": "positive",
    "confidence": 0.85
  },
  "signals": {
    "smart_money_accumulation": true,
    "whale_flow_dominant": false,
    "network_growth": true,
    "distribution_risk": false
  },
  "usage_policy": {
    "allowed": true,
    "recommended_weight": 1.0,
    "notes": "Data quality verified. Safe for automated use."
  }
}
```

---

## Shared Components (To Be Created)

Để giảm duplication, extract shared logic:

### `onchain_shared/` (proposed)
```
onchain_shared/
├── __init__.py
├── kill_switch/
│   ├── __init__.py
│   ├── base.py           # Base kill switch logic
│   ├── thresholds.py     # Shared threshold definitions
│   └── evaluator.py      # Signal evaluation logic
├── database/
│   ├── __init__.py
│   └── queries.py        # Shared SQL queries
└── models/
    ├── __init__.py
    └── signals.py        # Shared signal models
```

---

## Kill Switch Comparison

| Feature | `onchain_api` | `onchain_intel_product` |
|---------|---------------|-------------------------|
| States | OK, DEGRADED, BLOCKED | ACTIVE, DEGRADED, BLOCKED |
| Confidence checks | 3 levels | 1 level |
| Pipeline lag check | ✅ | ❌ |
| System resource check | ✅ | ❌ |
| Database health check | ✅ | ❌ |
| Anomaly detection | ✅ | ✅ |
| Manual override | ✅ | ❌ |

---

## Deployment Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     PRODUCTION NETWORK                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │   onchain_api        │    │   onchain_intel_product   │   │
│  │   (Port 8001)        │    │   (Port 8000)             │   │
│  │                      │    │                           │   │
│  │   INTERNAL ONLY      │    │   EXTERNAL/BotTrading     │   │
│  │   VPN Access         │    │   API Gateway             │   │
│  └───────────┬──────────┘    └─────────────┬─────────────┘   │
│              │                              │                │
│              └──────────────┬───────────────┘                │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │   PostgreSQL +   │                       │
│                    │   TimescaleDB    │                       │
│                    └──────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Action Items

1. ✅ Keep both modules with clear purposes
2. 🔲 Add this documentation to repo
3. 🔲 Consider creating `onchain_shared/` for common logic
4. 🔲 Standardize state naming (OK vs ACTIVE)
5. 🔲 Add integration tests between modules

---

## Decision Rationale

1. **Separation of Concerns:** Internal vs External APIs have different requirements
2. **Security:** External API can have stricter controls
3. **Simplicity:** External consumers get a simpler interface
4. **Flexibility:** Internal API can evolve faster
5. **Deployment:** Can scale independently

---

*Last Updated: January 17, 2026*
