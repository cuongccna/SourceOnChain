# OnChain Intelligence Data Product

> **⚠️ Module Purpose:** This is the **EXTERNAL/PRODUCTION API** for BotTrading systems.
> For internal API with full features, see `onchain_api/`.
> See [ARCHITECTURE_DECISION.md](../ARCHITECTURE_DECISION.md) for details.

Production-grade Bitcoin on-chain intelligence API optimized for BotTrading integration.

## 🎯 Module Overview

| Aspect | Description |
|--------|-------------|
| **Purpose** | Simplified API for external BotTrading consumers |
| **Target Users** | Trading bots, external systems, third-party integrations |
| **Key Endpoint** | `GET /api/v1/onchain/context` - Aggregated decision context |
| **Response Format** | Pre-aggregated with `usage_policy` for safe consumption |
| **Deployment** | Standalone, can be scaled independently |

### Comparison with `onchain_api/`

| Feature | `onchain_intel_product` (this) | `onchain_api` |
|---------|-------------------------------|---------------|
| Complexity | Simplified | Full-featured |
| Endpoints | 3 (context, audit, health) | 5+ (signal, health, audit, history, validation) |
| Database | psycopg2 (raw, fast) | SQLAlchemy ORM |
| Kill Switch | Basic (155 lines) | Advanced (552 lines) |
| Use Case | External BotTrading | Internal monitoring |

## 🚀 Hướng dẫn cài đặt và chạy

### 1. Yêu cầu hệ thống

- **Python 3.10+**
- **PostgreSQL 14+** (khuyến nghị có TimescaleDB)
- **Node.js** (cho PM2 - chỉ production)
- **Git**

### 2. Cấu hình môi trường

#### Tạo file .env

```bash
# Copy template và chỉnh sửa
cp env_template .env
```

#### Nội dung file .env cần cấu hình:

```bash
# Database Configuration
ONCHAIN_DATABASE_URL=postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals

# Kill Switch Thresholds
ONCHAIN_MIN_CONFIDENCE=0.60
ONCHAIN_STABILITY_THRESHOLD=0.70
ONCHAIN_COMPLETENESS_THRESHOLD=0.80

# Data Quality Thresholds  
ONCHAIN_MAX_DATA_AGE_HOURS=2.0
ONCHAIN_MAX_CONFLICTING_SIGNALS=2

# Usage Policy Weights
ONCHAIN_NORMAL_WEIGHT=1.0
ONCHAIN_DEGRADED_WEIGHT=0.3

# Logging Configuration
ONCHAIN_LOG_LEVEL=INFO

# API Configuration
ONCHAIN_API_HOST=0.0.0.0
ONCHAIN_API_PORT=8000
ONCHAIN_API_WORKERS=4

# Security (Production)
ONCHAIN_API_KEY=your_secure_api_key_here_change_in_production
```

#### Các biến môi trường quan trọng:

| Biến | Mô tả | Giá trị mặc định |
|------|-------|------------------|
| `ONCHAIN_DATABASE_URL` | URL kết nối PostgreSQL | `postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals` |
| `ONCHAIN_MIN_CONFIDENCE` | Ngưỡng confidence tối thiểu | `0.60` |
| `ONCHAIN_STABILITY_THRESHOLD` | Ngưỡng stability score | `0.70` |
| `ONCHAIN_COMPLETENESS_THRESHOLD` | Ngưỡng data completeness | `0.80` |
| `ONCHAIN_API_PORT` | Port API server | `8000` |
| `ONCHAIN_LOG_LEVEL` | Mức độ logging | `INFO` |

### 3. Thiết lập Database

#### Cách 1: Tự động (Khuyến nghị)

```bash
# Chạy script setup database
python setup_database.py
```

#### Cách 2: Thủ công

```bash
# 1. Tạo database và user (với quyền postgres)
sudo -u postgres psql
CREATE DATABASE bitcoin_onchain_signals;
CREATE USER onchain_user WITH PASSWORD 'onchain_pass';
GRANT ALL PRIVILEGES ON DATABASE bitcoin_onchain_signals TO onchain_user;
\q

# 2. Chạy schema migration
psql -U onchain_user -d bitcoin_onchain_signals -f database_schema.sql
```

#### Kiểm tra database:

```bash
# Test kết nối
python -c "
import psycopg2
import os
conn = psycopg2.connect('postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')
print('✅ Database connection successful')
conn.close()
"
```

### 4. Chạy ứng dụng tại Local

#### Windows Users (Khuyến nghị)

```cmd
# 1. Setup ban đầu (chỉ chạy 1 lần)
setup_windows.bat

# 2. Chạy development server
run_windows.bat
```

#### Linux/Mac Users

```bash
# Chạy development server
python run_local.py
```

Script này sẽ:
- ✅ Kiểm tra Python version
- ✅ Tạo .env từ template (nếu chưa có)
- ✅ Cài đặt dependencies
- ✅ Kiểm tra database connection
- ✅ Chạy database setup (nếu cần)
- ✅ Khởi động API server với auto-reload

#### Cách thủ công (Windows)

```cmd
# 1. Tạo virtual environment
python -m venv venv
venv\Scripts\activate.bat

# 2. Cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Tạo .env từ template
copy env_template .env
# Chỉnh sửa .env với thông tin database

# 4. Setup database
python setup_database.py

# 5. Chạy API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Cách thủ công (Linux/Mac)

```bash
# 1. Cài đặt dependencies
pip install -r requirements.txt

# 2. Kiểm tra database
python setup_database.py

# 3. Chạy API server (nếu port 8000 bị chiếm, dùng port khác)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# Hoặc: python launcher.py
```

#### Cách chạy thành công (Windows đã test)

```cmd
# Từ thư mục onchain_intel_product
python launcher.py
# Server sẽ chạy trên port 8001 nếu 8000 bị chiếm
```

#### Kiểm tra API:

- **API Base**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 5. Thiết lập PM2 cho Production

#### Cài đặt PM2:

```bash
# Cài đặt Node.js và PM2
npm install -g pm2
```

#### Cấu hình PM2:

File `ecosystem.config.js` đã được tạo sẵn với cấu hình:
- ✅ Auto-restart
- ✅ Log management
- ✅ Memory monitoring
- ✅ Cluster mode support

#### Chạy với PM2:

```bash
# Linux/Mac
./start_production.sh

# Windows (PowerShell)
# 1. Cài đặt dependencies
pip install -r requirements.txt

# 2. Khởi động với PM2
pm2 start ecosystem.config.js --env production

# 3. Kiểm tra status
pm2 status
pm2 logs onchain-intel-api
```

#### Quản lý PM2:

```bash
# Xem status
pm2 status

# Xem logs
pm2 logs onchain-intel-api

# Restart service
pm2 restart onchain-intel-api

# Stop service
pm2 stop onchain-intel-api

# Monitor processes
pm2 monit

# Auto-start on boot
pm2 startup
pm2 save
```

### 6. Test API

#### Test cơ bản:

```bash
# Health check
curl http://localhost:8000/health

# Get OnChain context
curl "http://localhost:8000/api/v1/onchain/context?asset=BTC&timeframe=1d"

# Get audit data
curl "http://localhost:8000/api/v1/onchain/audit/2024-01-15T12:00:00Z?asset=BTC&timeframe=1d"
```

#### Test với Python client:

```python
# Chạy example BotTrading client
python bottrading_client.py
```

### 7. Cấu trúc thư mục

```
onchain_intel_product/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── schemas.py             # Pydantic schemas
├── kill_switch.py         # Kill switch logic
├── audit.py               # Audit mechanism
├── bottrading_client.py   # Example client
├── setup_database.py      # Database setup script
├── run_local.py           # Local development runner
├── database_schema.sql    # Database schema
├── ecosystem.config.js    # PM2 configuration
├── start_production.sh    # Production startup script
├── requirements.txt       # Python dependencies
├── env_template          # Environment template
└── README.md             # This file
```

### 8. Troubleshooting

#### Database connection issues:

```bash
# Kiểm tra PostgreSQL service
sudo systemctl status postgresql

# Kiểm tra port
netstat -an | grep 5432

# Test connection
psql -U onchain_user -d bitcoin_onchain_signals -h localhost
```

#### API không start:

```bash
# Kiểm tra port đã được sử dụng
netstat -an | grep 8000

# Kiểm tra logs
tail -f logs/onchain-intel-error.log
```

#### Dependencies issues:

```bash
# Upgrade pip
pip install --upgrade pip

# Clean install
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### 9. Monitoring và Logs

#### Structured logs:

- **Location**: `logs/` directory
- **Format**: JSON structured logs
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

#### Key metrics to monitor:

- API response times
- Kill switch activations
- Database connection health
- Memory usage
- Error rates

### 10. Security Notes

⚠️ **Production Security Checklist:**

- [ ] Thay đổi `ONCHAIN_API_KEY` mặc định
- [ ] Sử dụng HTTPS trong production
- [ ] Cấu hình firewall cho database
- [ ] Backup database định kỳ
- [ ] Monitor logs cho suspicious activity
- [ ] Update dependencies thường xuyên

---

## 📞 Support

Nếu gặp vấn đề, kiểm tra:
1. **Logs**: `logs/onchain-intel-error.log`
2. **Database**: Connection và schema
3. **Environment**: File .env và biến môi trường
4. **Dependencies**: Python packages version

**API Documentation**: http://localhost:8000/docs (hoặc 8001 nếu port 8000 bị chiếm)

## Troubleshooting Cập Nhật

### Lỗi port 8000 bị chiếm:
1. Kiểm tra process đang dùng port:
   ```cmd
   netstat -ano | findstr 8000
   ```

2. Kill process và chạy lại:
   ```cmd
   taskkill /PID <PID_NUMBER> /F
   python launcher.py
   ```

3. Hoặc chạy trên port khác:
   ```cmd
   python -c "from main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8001)"
   ```

### Lỗi database connection:
1. Kiểm tra PostgreSQL đang chạy:
   ```cmd
   netstat -ano | findstr 5432
   ```

2. Test kết nối database:
   ```python
   python -c "import psycopg2; psycopg2.connect('postgresql://onchain_user:Cuongnv123456@localhost:5432/bitcoin_onchain_signals'); print('OK')"
   ```

### Lỗi import module:
- Đảm bảo chạy từ thư mục `onchain_intel_product`
- Virtual environment đã được activate
- Tất cả dependencies đã được cài đặt