#!/usr/bin/env python3
"""
Local development runner for OnChain Intelligence Data Product.
"""

import os
import sys
import subprocess
import time
import psycopg2
from pathlib import Path
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def check_python_version():
    """Check Python version compatibility."""
    if sys.version_info < (3, 10):
        logger.error("Python 3.10+ is required")
        return False
    
    logger.info(f"✅ Python version: {sys.version}")
    return True


def check_env_file():
    """Check if .env file exists."""
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning("⚠️  .env file not found")
        logger.info("Creating .env from template...")
        
        template_file = Path("env_template")
        if template_file.exists():
            import shutil
            shutil.copy("env_template", ".env")
            logger.info("✅ .env file created from template")
            logger.warning("🔧 Please edit .env file with your actual configuration")
            return True
        else:
            logger.error("❌ env_template not found")
            return False
    
    logger.info("✅ .env file exists")
    return True


def load_env_variables():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("✅ Environment variables loaded")
        return True
    except ImportError:
        logger.warning("python-dotenv not installed, using system environment")
        return True
    except Exception as e:
        logger.error(f"Failed to load environment variables: {e}")
        return False


def check_database_connection():
    """Check database connection."""
    database_url = os.getenv('ONCHAIN_DATABASE_URL')
    if not database_url:
        logger.error("❌ ONCHAIN_DATABASE_URL not set in environment")
        return False
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Database connection successful")
        logger.info(f"Database version: {version[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.info("💡 Make sure PostgreSQL is running and database is created")
        logger.info("💡 Run: python setup_database.py")
        return False


def install_dependencies():
    """Install Python dependencies."""
    logger.info("📦 Installing dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True, capture_output=True, text=True)
        
        logger.info("✅ Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install dependencies: {e.stderr}")
        return False


def run_database_setup():
    """Run database setup if needed."""
    logger.info("🗄️  Checking database setup...")
    
    try:
        # Try to import and run setup
        from setup_database import verify_database_setup
        
        if verify_database_setup():
            logger.info("✅ Database setup verified")
            return True
        else:
            logger.warning("⚠️  Database setup incomplete, running setup...")
            from setup_database import main as setup_main
            setup_main()
            return True
            
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        logger.info("💡 Please run: python setup_database.py")
        return False


def start_api_server():
    """Start the FastAPI server."""
    logger.info("🚀 Starting OnChain Intelligence API server...")
    
    host = os.getenv('ONCHAIN_API_HOST', '0.0.0.0')
    port = int(os.getenv('ONCHAIN_API_PORT', 8000))
    workers = int(os.getenv('ONCHAIN_API_WORKERS', 1))
    log_level = os.getenv('ONCHAIN_LOG_LEVEL', 'info').lower()
    
    try:
        # Start uvicorn server
        cmd = [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", host,
            "--port", str(port),
            "--log-level", log_level,
            "--reload"  # Enable auto-reload for development
        ]
        
        if workers > 1:
            cmd.extend(["--workers", str(workers)])
        
        logger.info(f"🌐 Starting server at http://{host}:{port}")
        logger.info(f"📚 API docs will be available at http://{host}:{port}/docs")
        logger.info("🔄 Auto-reload enabled for development")
        logger.info("Press Ctrl+C to stop the server")
        
        # Run the server
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Server failed to start: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False
    
    return True


def main():
    """Main function to run local development server."""
    
    logger.info("🚀 OnChain Intelligence Data Product - Local Development")
    logger.info("=" * 60)
    
    # Step 1: Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Step 2: Check .env file
    if not check_env_file():
        sys.exit(1)
    
    # Step 3: Load environment variables
    if not load_env_variables():
        sys.exit(1)
    
    # Step 4: Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Step 5: Check database connection
    if not check_database_connection():
        logger.info("🔧 Setting up database...")
        if not run_database_setup():
            sys.exit(1)
    
    # Step 6: Start API server
    logger.info("=" * 60)
    if not start_api_server():
        sys.exit(1)
    
    logger.info("✅ Local development session completed")


if __name__ == "__main__":
    main()