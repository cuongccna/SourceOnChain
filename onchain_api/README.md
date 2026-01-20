# OnChain API - Internal API

> **⚠️ Module Purpose:** This is the **INTERNAL API** with full features for monitoring and development.
> For production BotTrading API, see `onchain_intel_product/`.
> See [ARCHITECTURE_DECISION.md](../ARCHITECTURE_DECISION.md) for details.

Full-featured internal Bitcoin on-chain intelligence API.

## 🎯 Module Overview

| Aspect | Description |
|--------|-------------|
| **Purpose** | Full-featured internal API for monitoring, debugging, validation |
| **Target Users** | Internal dashboards, monitoring systems, developers |
| **Key Features** | Multiple endpoints, detailed logging, metrics, rate limiting |
| **Database** | SQLAlchemy ORM with connection pooling |
| **Deployment** | Internal network only (VPN access) |

## Comparison with `onchain_intel_product/`

| Feature | `onchain_api` (this) | `onchain_intel_product` |
|---------|---------------------|------------------------|
| Complexity | Full-featured | Simplified |
| Endpoints | 5+ (signal, health, audit, history, validation) | 3 (context, audit, health) |
| Database | SQLAlchemy ORM | psycopg2 (raw) |
| Kill Switch | Advanced (552 lines, multiple checks) | Basic (155 lines) |
| Metrics | Prometheus integration | None |
| Rate Limiting | Per-client | None |
| Use Case | Internal monitoring | External BotTrading |

## 📁 Structure

```
onchain_api/
├── app/
│   ├── main.py           # FastAPI application
│   └── routers/
│       ├── signal.py     # Signal endpoint
│       ├── health.py     # Health check endpoint
│       ├── audit.py      # Audit endpoint
│       ├── history.py    # History endpoint
│       └── validation.py # Validation endpoint
├── config/
│   └── settings.py       # Configuration with Pydantic
├── schemas/
│   ├── models.py         # Data models
│   └── responses.py      # Response schemas
├── services/
│   ├── kill_switch.py    # Advanced kill switch (552 lines)
│   └── signal_service.py # Signal processing service
└── utils/
    ├── logging.py        # Structured logging setup
    ├── metrics.py        # Prometheus metrics
    └── rate_limiter.py   # Rate limiting
```

## 🚀 Endpoints

### `GET /api/v1/onchain/signal`
Get raw signal data with detailed breakdown.

**Response:** Detailed signal with metadata, verification, and internal metrics.

### `GET /api/v1/onchain/health`
Comprehensive health check with system status.

**Response:** Detailed health including database, pipeline, and resource status.

### `GET /api/v1/onchain/audit/{timestamp}`
Get audit trail for reproducibility.

### `GET /api/v1/onchain/history`
Get historical signal data.

### `GET /api/v1/onchain/validate`
Run validation checks on signals.

## ⚙️ Configuration

Environment variables (prefix: `ONCHAIN_API_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | required |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENABLE_METRICS` | Enable Prometheus metrics | `true` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate limit window (seconds) | `60` |

## 🔧 Running

```bash
# Development
cd onchain_api
uvicorn app.main:app --reload --port 8001

# Production (internal network)
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

## 📊 Metrics

Prometheus metrics available at `/metrics`:

- `onchain_api_request_count` - Total request count
- `onchain_api_request_duration` - Request duration histogram
- `onchain_api_signal_status` - Signal status distribution
- `onchain_api_kill_switch_activations` - Kill switch activations

---

*See [ARCHITECTURE_DECISION.md](../ARCHITECTURE_DECISION.md) for more details on the module separation decision.*
