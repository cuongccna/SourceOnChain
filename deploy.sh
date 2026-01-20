#!/bin/bash
# =============================================================================
# OnChain Intelligence - Deployment Script
# =============================================================================
# Usage: ./deploy.sh [command]
# Commands:
#   install    - First time setup
#   update     - Pull latest code and restart
#   start      - Start the service
#   stop       - Stop the service
#   restart    - Restart the service
#   status     - Check service status
#   logs       - View logs
#   db-init    - Initialize database schema
#   db-migrate - Run database migrations
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Configuration - Load from .env
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Please copy .env.production.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' "$ENV_FILE" | xargs)

# App configuration
APP_NAME="${PM2_APP_NAME:-onchain-intelligence}"
APP_DIR="$SCRIPT_DIR"
PYTHON_VERSION="3.11"
VENV_DIR="$APP_DIR/.venv"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 not found. Please install Python ${PYTHON_VERSION}+"
        exit 1
    fi
    
    # Check PM2
    if ! command -v pm2 &> /dev/null; then
        log_error "PM2 not found. Install with: npm install -g pm2"
        exit 1
    fi
    
    # Check PostgreSQL client
    if ! command -v psql &> /dev/null; then
        log_warn "psql not found. Database operations may fail."
    fi
}

# =============================================================================
# Commands
# =============================================================================

cmd_install() {
    log_info "Starting first-time installation..."
    
    check_requirements
    
    # Create virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate and install dependencies
    log_info "Installing Python dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$APP_DIR/requirements.txt"
    
    # Initialize database
    cmd_db_init
    
    # Setup PM2
    log_info "Setting up PM2..."
    pm2 start "$APP_DIR/ecosystem.config.js"
    pm2 save
    
    log_info "Installation complete!"
    log_info "API running on port ${ONCHAIN_API_PORT:-8500}"
}

cmd_update() {
    log_info "Updating application..."
    
    # Pull latest code
    log_info "Pulling latest code from git..."
    cd "$APP_DIR"
    git pull origin main
    
    # Update dependencies
    log_info "Updating Python dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r "$APP_DIR/requirements.txt"
    
    # Restart
    cmd_restart
    
    log_info "Update complete!"
}

cmd_start() {
    log_info "Starting $APP_NAME..."
    pm2 start "$APP_DIR/ecosystem.config.js"
    pm2 save
    log_info "Started. Use 'pm2 status' to check."
}

cmd_stop() {
    log_info "Stopping $APP_NAME..."
    pm2 stop "$APP_NAME" || true
    pm2 stop "${APP_NAME}-scheduler" || true
    log_info "Stopped."
}

cmd_restart() {
    log_info "Restarting $APP_NAME..."
    pm2 restart "$APP_NAME" || cmd_start
    pm2 restart "${APP_NAME}-scheduler" || true
    log_info "Restarted."
}

cmd_status() {
    pm2 status
}

cmd_logs() {
    pm2 logs "$APP_NAME" --lines 100
}

cmd_db_init() {
    log_info "Initializing database..."
    
    # Check required env vars
    if [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
        log_error "Database configuration missing in .env"
        exit 1
    fi
    
    # Run schema
    if [ -f "$APP_DIR/schema.sql" ]; then
        log_info "Running schema.sql..."
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -f "$APP_DIR/schema.sql"
        log_info "Database schema created."
    else
        log_error "schema.sql not found!"
        exit 1
    fi
}

cmd_db_migrate() {
    log_info "Running database migrations..."
    # Add migration logic here if needed
    log_info "No pending migrations."
}

cmd_test() {
    log_info "Running tests..."
    source "$VENV_DIR/bin/activate"
    cd "$APP_DIR"
    python -m pytest tests/ -v
}

cmd_health() {
    log_info "Checking API health..."
    PORT="${ONCHAIN_API_PORT:-8500}"
    
    response=$(curl -s "http://localhost:$PORT/health" || echo "FAILED")
    
    if [[ "$response" == *"healthy"* ]]; then
        log_info "API is healthy!"
        echo "$response" | python3 -m json.tool
    else
        log_error "API health check failed!"
        echo "$response"
        exit 1
    fi
}

# =============================================================================
# Main
# =============================================================================

case "${1:-help}" in
    install)
        cmd_install
        ;;
    update)
        cmd_update
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    db-init)
        cmd_db_init
        ;;
    db-migrate)
        cmd_db_migrate
        ;;
    test)
        cmd_test
        ;;
    health)
        cmd_health
        ;;
    *)
        echo "OnChain Intelligence - Deployment Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  install     First time setup (venv, deps, db, pm2)"
        echo "  update      Pull code and restart"
        echo "  start       Start the service"
        echo "  stop        Stop the service"
        echo "  restart     Restart the service"
        echo "  status      Check PM2 status"
        echo "  logs        View application logs"
        echo "  db-init     Initialize database schema"
        echo "  db-migrate  Run database migrations"
        echo "  test        Run test suite"
        echo "  health      Check API health"
        echo ""
        ;;
esac
