-- =============================================================================
-- OnChain Intelligence - Database Schema
-- =============================================================================
-- Run this script to create all required tables
-- Usage: psql -U your_user -d your_database -f schema.sql
-- =============================================================================

-- Create extension for UUID if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Table: onchain_metrics
-- Stores raw blockchain, mempool, and whale metrics
-- =============================================================================
CREATE TABLE IF NOT EXISTS onchain_metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    
    -- Blockchain metrics
    block_height INTEGER,
    blocks_analyzed INTEGER,
    total_transactions INTEGER,
    avg_block_size DOUBLE PRECISION,
    avg_txs_per_block DOUBLE PRECISION,
    
    -- Mempool metrics
    pending_txs INTEGER,
    mempool_size_mb DOUBLE PRECISION,
    total_fees_btc DOUBLE PRECISION,
    fastest_fee INTEGER,
    hour_fee INTEGER,
    
    -- Whale metrics
    whale_tx_count INTEGER,
    whale_volume_btc DOUBLE PRECISION,
    whale_inflow DOUBLE PRECISION,
    whale_outflow DOUBLE PRECISION,
    net_whale_flow DOUBLE PRECISION,
    whale_dominance DOUBLE PRECISION,
    
    -- Data quality
    data_source VARCHAR(50),
    data_hash VARCHAR(64),
    
    -- Indexes
    CONSTRAINT onchain_metrics_unique UNIQUE (timestamp, asset)
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON onchain_metrics (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_asset_time ON onchain_metrics (asset, timestamp DESC);

-- =============================================================================
-- Table: onchain_signals
-- Stores computed signals and scores
-- =============================================================================
CREATE TABLE IF NOT EXISTS onchain_signals (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
    
    -- Signals (boolean flags)
    smart_money_accumulation BOOLEAN DEFAULT FALSE,
    whale_flow_dominant BOOLEAN DEFAULT FALSE,
    network_growth BOOLEAN DEFAULT FALSE,
    distribution_risk BOOLEAN DEFAULT FALSE,
    exchange_inflow BOOLEAN DEFAULT FALSE,
    exchange_outflow BOOLEAN DEFAULT FALSE,
    
    -- Computed values
    onchain_score INTEGER,
    bias VARCHAR(20),
    confidence DOUBLE PRECISION,
    
    -- State
    state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    block_reason TEXT,
    
    -- Data quality
    completeness_score DOUBLE PRECISION,
    data_age_seconds DOUBLE PRECISION,
    is_stale BOOLEAN DEFAULT FALSE,
    
    -- Indexes
    CONSTRAINT onchain_signals_unique UNIQUE (timestamp, asset, timeframe)
);

-- Indexes for queries
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON onchain_signals (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_asset_time ON onchain_signals (asset, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_state ON onchain_signals (state);

-- =============================================================================
-- Table: whale_transactions
-- Stores individual whale transactions for analysis
-- =============================================================================
CREATE TABLE IF NOT EXISTS whale_transactions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Transaction info
    txid VARCHAR(64) NOT NULL,
    block_height INTEGER,
    
    -- Value
    value_btc DOUBLE PRECISION NOT NULL,
    value_usd DOUBLE PRECISION,
    
    -- Classification
    tier VARCHAR(20) NOT NULL,  -- 'large', 'whale', 'ultra_whale', 'leviathan'
    flow_type VARCHAR(20),      -- 'inflow', 'outflow', 'internal'
    
    -- Addresses (hashed for privacy)
    input_count INTEGER,
    output_count INTEGER,
    
    -- Metadata
    fee_btc DOUBLE PRECISION,
    fee_rate DOUBLE PRECISION,
    
    CONSTRAINT whale_tx_unique UNIQUE (txid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_whale_tx_timestamp ON whale_transactions (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_whale_tx_tier ON whale_transactions (tier);
CREATE INDEX IF NOT EXISTS idx_whale_tx_block ON whale_transactions (block_height);

-- =============================================================================
-- Table: data_source_health
-- Tracks health of data sources for failover
-- =============================================================================
CREATE TABLE IF NOT EXISTS data_source_health (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    last_success TIMESTAMPTZ,
    last_failure TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    avg_response_time_ms DOUBLE PRECISION,
    total_requests INTEGER DEFAULT 0,
    total_failures INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default sources
INSERT INTO data_source_health (source_name, status) 
VALUES 
    ('mempool_space', 'unknown'),
    ('blockchain_info', 'unknown'),
    ('blockcypher', 'unknown')
ON CONFLICT (source_name) DO NOTHING;

-- =============================================================================
-- Table: system_state
-- Stores system state and configuration
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_state (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Views for common queries
-- =============================================================================

-- Latest metrics view
CREATE OR REPLACE VIEW v_latest_metrics AS
SELECT * FROM onchain_metrics
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 1;

-- Latest signals view
CREATE OR REPLACE VIEW v_latest_signals AS
SELECT * FROM onchain_signals
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 1;

-- Hourly statistics view
CREATE OR REPLACE VIEW v_hourly_stats AS
SELECT 
    date_trunc('hour', timestamp) as hour,
    asset,
    AVG(onchain_score) as avg_score,
    MIN(onchain_score) as min_score,
    MAX(onchain_score) as max_score,
    AVG(confidence) as avg_confidence,
    COUNT(*) as data_points,
    SUM(CASE WHEN state = 'BLOCKED' THEN 1 ELSE 0 END) as blocked_count
FROM onchain_signals
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY date_trunc('hour', timestamp), asset
ORDER BY hour DESC;

-- =============================================================================
-- Functions
-- =============================================================================

-- Function to clean old data (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    DELETE FROM onchain_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
    DELETE FROM onchain_signals WHERE timestamp < NOW() - INTERVAL '30 days';
    DELETE FROM whale_transactions WHERE timestamp < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Permissions (run as superuser)
-- =============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_user;

-- =============================================================================
-- Done
-- =============================================================================
