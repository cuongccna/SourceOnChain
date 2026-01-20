#!/bin/bash

# OnChain Intelligence Data Product - Production Startup Script

set -e

echo "🚀 Starting OnChain Intelligence Data Product..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"

echo "📁 Project directory: $PROJECT_DIR"

# Create logs directory
mkdir -p "$LOG_DIR"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    echo "🔧 Loading environment variables..."
    export $(cat "$PROJECT_DIR/.env" | grep -v '^#' | xargs)
else
    echo -e "${RED}❌ .env file not found! Please create it from env_template${NC}"
    exit 1
fi

# Database setup check
echo "🗄️  Checking database connection..."
python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.getenv('ONCHAIN_DATABASE_URL'))
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ PM2 is not installed. Installing globally...${NC}"
    npm install -g pm2
fi

# Stop existing processes
echo "🛑 Stopping existing processes..."
pm2 stop onchain-intel-api 2>/dev/null || echo "No existing process to stop"
pm2 delete onchain-intel-api 2>/dev/null || echo "No existing process to delete"

# Start with PM2
echo "🚀 Starting OnChain Intelligence API with PM2..."
pm2 start ecosystem.config.js --env production

# Show status
echo "📊 Process status:"
pm2 status

# Show logs
echo -e "${GREEN}✅ OnChain Intelligence Data Product started successfully!${NC}"
echo ""
echo "📋 Management commands:"
echo "  pm2 status                    - Show process status"
echo "  pm2 logs onchain-intel-api    - Show logs"
echo "  pm2 restart onchain-intel-api - Restart service"
echo "  pm2 stop onchain-intel-api    - Stop service"
echo "  pm2 monit                     - Monitor processes"
echo ""
echo "🌐 API will be available at: http://localhost:8000"
echo "📚 API documentation: http://localhost:8000/docs"
echo ""
echo "📝 Logs location: $LOG_DIR/"