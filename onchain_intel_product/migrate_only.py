#!/usr/bin/env python3
"""
Schema migration only - assumes database and user already exist.
"""

import os
import sys
import psycopg2
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


def run_migration_only():
    """Run schema migration only."""
    
    # Parse database URL from environment
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:Cuongnv123456@localhost:5432/bitcoin_onchain_signals')
    
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    
    conn_params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'onchain_user',
        'password': parsed.password or 'Cuongnv123456',
        'database': parsed.path.lstrip('/') or 'bitcoin_onchain_signals'
    }
    
    logger.info(f"Connecting to database: {conn_params['database']}")
    logger.info(f"Using user: {conn_params['user']}")
    
    try:
        # Test connection first
        conn = psycopg2.connect(**conn_params)
        conn.close()
        logger.info("✅ Database connection successful")
        
        # Read schema file
        schema_file = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Connect and execute schema
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        logger.info("Running database schema migration...")
        
        # Split SQL by statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        success_count = 0
        skip_count = 0
        
        for i, statement in enumerate(statements):
            # Skip comments and empty statements
            if statement.startswith('--') or not statement:
                continue
                
            # Skip connection commands
            if statement.startswith('\\c'):
                continue
                
            try:
                cursor.execute(statement)
                success_count += 1
                logger.debug(f"✅ Statement {i+1}: Success")
            except Exception as e:
                if "already exists" in str(e).lower():
                    skip_count += 1
                    logger.debug(f"⏭️  Statement {i+1}: Skipped (already exists)")
                else:
                    logger.warning(f"⚠️  Statement {i+1}: {str(e)[:100]}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Schema migration completed!")
        logger.info(f"   - Executed: {success_count} statements")
        logger.info(f"   - Skipped: {skip_count} statements")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("🗄️  OnChain Intelligence - Schema Migration Only")
    logger.info("=" * 50)
    
    if run_migration_only():
        logger.info("✅ Migration completed successfully!")
        logger.info("You can now start the API service.")
    else:
        logger.error("❌ Migration failed!")
        sys.exit(1)