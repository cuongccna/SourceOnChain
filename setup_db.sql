-- =============================================================================
-- OnChain Intelligence - Database Setup (Run as Superuser/postgres)
-- =============================================================================
-- Run this FIRST as postgres superuser:
-- sudo -u postgres psql -f setup_db.sql
-- =============================================================================

-- Create database if not exists
SELECT 'CREATE DATABASE bitcoin_onchain_signals'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'bitcoin_onchain_signals')\gexec

-- Create user (change password!)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'onchain_user') THEN
        CREATE USER onchain_user WITH ENCRYPTED PASSWORD 'CHANGE_THIS_PASSWORD';
    END IF;
END
$$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE bitcoin_onchain_signals TO onchain_user;

-- Connect to the database
\c bitcoin_onchain_signals

-- Grant schema permissions (REQUIRED for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO onchain_user;
GRANT CREATE ON SCHEMA public TO onchain_user;

-- Make onchain_user owner of public schema objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO onchain_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO onchain_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO onchain_user;

-- =============================================================================
-- Now run schema.sql as onchain_user:
-- PGPASSWORD='your_password' psql -h localhost -U onchain_user -d bitcoin_onchain_signals -f schema.sql
-- =============================================================================
