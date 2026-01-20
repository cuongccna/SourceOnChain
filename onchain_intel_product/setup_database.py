#!/usr/bin/env python3
"""
Database setup script for OnChain Intelligence Data Product.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import structlog

logger = structlog.get_logger(__name__)


def create_database_and_user():
    """Create database and user if they don't exist."""
    
    # Get admin password from environment or prompt user
    admin_password = os.getenv('DB_ADMIN_PASSWORD')
    if not admin_password:
        print("PostgreSQL admin password not found in environment.")
        print("Please enter the password for PostgreSQL user 'postgres':")
        import getpass
        admin_password = getpass.getpass("Password: ")
    
    # Default PostgreSQL connection (as superuser)
    admin_conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', 5432),
        'user': os.getenv('DB_ADMIN_USER', 'postgres'),
        'password': admin_password,
        'database': 'postgres'
    }
    
    # Target database and user - extract from ONCHAIN_DATABASE_URL or use defaults
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')
    
    # Parse database URL to extract components
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    target_db = parsed.path.lstrip('/') if parsed.path else 'bitcoin_onchain_signals'
    target_user = parsed.username if parsed.username else 'onchain_user'
    target_password = parsed.password if parsed.password else 'onchain_pass'
    
    logger.info(f"Target database: {target_db}")
    logger.info(f"Target user: {target_user}")
    
    try:
        # Connect as admin
        conn = psycopg2.connect(**admin_conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        if not cursor.fetchone():
            logger.info(f"Creating database: {target_db}")
            cursor.execute(f'CREATE DATABASE "{target_db}"')
        else:
            logger.info(f"Database {target_db} already exists")
        
        # Check if user exists
        cursor.execute("SELECT 1 FROM pg_user WHERE usename = %s", (target_user,))
        if not cursor.fetchone():
            logger.info(f"Creating user: {target_user}")
            cursor.execute(f"CREATE USER {target_user} WITH PASSWORD %s", (target_password,))
        else:
            logger.info(f"User {target_user} already exists")
        
        # Grant privileges
        cursor.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{target_db}" TO {target_user}')
        logger.info(f"Granted privileges on {target_db} to {target_user}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create database/user: {e}")
        return False


def run_schema_migration():
    """Run database schema migration."""
    
    # Parse database URL from environment
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')
    
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    # Target database connection
    conn_params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'onchain_user',
        'password': parsed.password or 'onchain_pass',
        'database': parsed.path.lstrip('/') or 'bitcoin_onchain_signals'
    }
    
    try:
        # Read schema file
        schema_file = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Connect and execute schema
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        logger.info("Running database schema migration...")
        
        # Split SQL by statements (simple approach)
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements):
            # Skip comments and empty statements
            if statement.startswith('--') or not statement:
                continue
                
            # Skip connection commands (handled by psycopg2)
            if statement.startswith('\\c'):
                continue
                
            try:
                cursor.execute(statement)
                logger.debug(f"Executed statement {i+1}/{len(statements)}")
            except Exception as e:
                # Some statements might fail if objects already exist
                if "already exists" in str(e).lower():
                    logger.debug(f"Statement {i+1} skipped (already exists): {str(e)[:100]}")
                else:
                    logger.warning(f"Statement {i+1} failed: {str(e)[:200]}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Database schema migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        return False


def verify_database_setup():
    """Verify database setup by checking key tables."""
    
    # Parse database URL from environment
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')
    
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    conn_params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'onchain_user',
        'password': parsed.password or 'onchain_pass',
        'database': parsed.path.lstrip('/') or 'bitcoin_onchain_signals'
    }
    
    required_tables = [
        'onchain_scores',
        'signal_calculations', 
        'signal_verification_logs',
        'signal_anomalies',
        'audit_calculations'
    ]
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        logger.info("Verifying database setup...")
        
        for table in required_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = %s AND table_schema = 'public'
            """, (table,))
            
            if cursor.fetchone()[0] == 0:
                logger.error(f"Required table missing: {table}")
                return False
            else:
                logger.info(f"✓ Table exists: {table}")
        
        # Check TimescaleDB extension
        cursor.execute("SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'")
        if cursor.fetchone()[0] == 0:
            logger.warning("TimescaleDB extension not found - time-series optimization disabled")
        else:
            logger.info("✓ TimescaleDB extension enabled")
        
        # Test sample data
        cursor.execute("SELECT COUNT(*) FROM onchain_scores")
        score_count = cursor.fetchone()[0]
        logger.info(f"✓ OnChain scores table has {score_count} records")
        
        cursor.close()
        conn.close()
        
        logger.info("Database verification completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False


def test_existing_connection():
    """Test if we can connect with existing database credentials."""
    
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')
    
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    conn_params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'onchain_user',
        'password': parsed.password or 'onchain_pass',
        'database': parsed.path.lstrip('/') or 'bitcoin_onchain_signals'
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        conn.close()
        logger.info("✅ Database connection successful with existing credentials")
        return True
    except Exception as e:
        logger.warning(f"Cannot connect with existing credentials: {e}")
        return False


def main():
    """Main setup function."""
    
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
    
    logger.info("Starting OnChain Intelligence Database Setup")
    
    # Step 0: Test if database already exists and accessible
    if test_existing_connection():
        logger.info("Database and user already exist and accessible")
        create_needed = False
    else:
        logger.info("Need to create database and user")
        create_needed = True
    
    # Step 1: Create database and user (only if needed)
    if create_needed:
        if not create_database_and_user():
            logger.error("Failed to create database and user")
            logger.info("💡 If database already exists, make sure PostgreSQL is running and credentials are correct")
            sys.exit(1)
    
    # Step 2: Run schema migration
    if not run_schema_migration():
        logger.error("Failed to run schema migration")
        sys.exit(1)
    
    # Step 3: Verify setup
    if not verify_database_setup():
        logger.error("Database verification failed")
        sys.exit(1)
    
    logger.info("✅ OnChain Intelligence Database Setup Complete!")
    logger.info("You can now start the API service.")


if __name__ == "__main__":
    main()