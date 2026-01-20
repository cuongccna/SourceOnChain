# OnChain Intelligence - VPS Deployment Guide

## Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/onchain-intelligence.git
cd onchain-intelligence
```

### 2. Configure Environment
```bash
# Copy example config
cp .env.production.example .env

# Edit with your values
nano .env
```

**Required settings:**
```env
# API Port (8500+ recommended)
ONCHAIN_API_PORT=8500

# Database (fill in your credentials)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bitcoin_onchain_signals
DB_USER=your_user
DB_PASSWORD=your_password
```

### 3. Deploy
```bash
# Make deploy script executable
chmod +x deploy.sh

# First time installation
./deploy.sh install

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Database Setup
```bash
# Create database (as postgres user)
sudo -u postgres psql

CREATE DATABASE bitcoin_onchain_signals;
CREATE USER your_user WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE bitcoin_onchain_signals TO your_user;
\q

# Run schema
./deploy.sh db-init
```

### 5. Start Service
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Enable auto-start on boot
```

## Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh install` | First time setup |
| `./deploy.sh update` | Pull code & restart |
| `./deploy.sh start` | Start service |
| `./deploy.sh stop` | Stop service |
| `./deploy.sh restart` | Restart service |
| `./deploy.sh status` | PM2 status |
| `./deploy.sh logs` | View logs |
| `./deploy.sh health` | Check API health |

## API Endpoints

Base URL: `http://your-vps-ip:8500`

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/onchain/context` | 🎯 Main BotTrading endpoint |
| `GET /api/v1/onchain/quality` | Data quality verification |
| `GET /api/v1/onchain/metrics` | Detailed metrics |
| `GET /api/v1/onchain/signals` | Current signals |
| `GET /api/v1/onchain/whale` | Whale activity |
| `GET /api/v1/onchain/history` | Historical data |
| `GET /api/v1/onchain/statistics` | Score statistics |
| `GET /docs` | Swagger documentation |

## Example Request

```bash
curl "http://localhost:8500/api/v1/onchain/context?asset=BTC&timeframe=1h"
```

Response:
```json
{
  "product": "onchain_intelligence",
  "asset": "BTC",
  "state": "ACTIVE",
  "decision_context": {
    "onchain_score": 35,
    "bias": "negative",
    "confidence": 0.85
  },
  "signals": {
    "smart_money_accumulation": false,
    "distribution_risk": true
  },
  "verification": {
    "invariants_passed": true,
    "data_completeness": 1.0,
    "is_stale": false
  },
  "usage_policy": {
    "allowed": true,
    "recommended_weight": 0.3
  }
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (with Fallback)             │
├─────────────────────────────────────────────────────────────┤
│  mempool.space (Primary) → blockchain.info → blockcypher    │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    On-chain Collector
                              ↓
                    Normalize & Verify
                              ↓
                 ┌────────────────────────┐
                 │   Data Quality Check   │
                 │  - Completeness score  │
                 │  - Lag detection       │
                 │  - BLOCK state         │
                 └────────────────────────┘
                              ↓
                   Signal + Confidence
                              ↓
                    ┌────────────────┐
                    │   PostgreSQL   │
                    └────────────────┘
                              ↓
                         BotTrading
```

## States

| State | Description | Action |
|-------|-------------|--------|
| `ACTIVE` | Data quality good | Normal use |
| `DEGRADED` | Some issues | Use with reduced weight (0.3x) |
| `BLOCKED` | Critical issues | DO NOT use |

## Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 80;
    server_name onchain.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8500;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Troubleshooting

### Port already in use
```bash
# Check what's using the port
lsof -i :8500

# Kill process
kill -9 <PID>
```

### Database connection failed
```bash
# Check PostgreSQL is running
systemctl status postgresql

# Test connection
psql -h localhost -U your_user -d bitcoin_onchain_signals
```

### PM2 issues
```bash
# Restart PM2
pm2 kill
pm2 start ecosystem.config.js

# Check logs
pm2 logs onchain-intelligence --lines 200
```

## Security Notes

1. **Never commit `.env`** - It's in `.gitignore`
2. **Use strong DB password** - At least 16 characters
3. **Firewall** - Only expose port 8500 if needed externally
4. **API Key** - Set `ONCHAIN_API_KEY` for authentication (optional)
