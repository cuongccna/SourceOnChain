-- OnChain Intelligence Data Product Database Schema
-- PostgreSQL 14+ with TimescaleDB extension

-- Create database and user (run as postgres superuser)
-- CREATE DATABASE bitcoin_onchain_signals;
-- CREATE USER onchain_user WITH PASSWORD 'onchain_pass';
-- GRANT ALL PRIVILEGES ON DATABASE bitcoin_onchain_signals TO onchain_user;

-- Connect to bitcoin_onchain_signals database
\c bitcoin_onchain_signals;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =====================================================
-- OnChain Scores Table (Main aggregated scores)
-- =====================================================
CREATE TABLE IF NOT EXISTS onchain_scores (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
    
    -- Core scores
    onchain_score DECIMAL(5,2) CHECK (onchain_score >= 0 AND onchain_score <= 100),
    confidence DECIMAL(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    bias VARCHAR(10) NOT NULL CHECK (bias IN ('positive', 'neutral', 'negative')),
    
    -- Component scores
    network_health_score DECIMAL(5,2) CHECK (network_health_score >= 0 AND network_health_score <= 30),
    capital_flow_score DECIMAL(5,2) CHECK (capital_flow_score >= 0 AND capital_flow_score <= 30),
    smart_money_score DECIMAL(5,2) CHECK (smart_money_score >= 0 AND smart_money_score <= 40),
    risk_penalty DECIMAL(5,2) CHECK (risk_penalty >= 0),
    
    -- Signal metadata
    signal_count INTEGER NOT NULL DEFAULT 0,
    active_signals INTEGER NOT NULL DEFAULT 0,
    conflicting_signals INTEGER NOT NULL DEFAULT 0,
    
    -- Data quality
    data_completeness DECIMAL(4,3) NOT NULL CHECK (data_completeness >= 0 AND data_completeness <= 1),
    calculation_time_ms INTEGER NOT NULL DEFAULT 0,
    
    -- Audit fields
    input_data_hash VARCHAR(64),
    calculation_hash VARCHAR(64),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(timestamp, asset, timeframe)
);

-- Create hypertable for time-series optimization
SELECT create_hypertable('onchain_scores', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_onchain_scores_asset_timeframe_timestamp 
ON onchain_scores (asset, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_onchain_scores_created_at 
ON onchain_scores (created_at DESC);

-- =====================================================
-- Signal Calculations Table (Individual signals)
-- =====================================================
CREATE TABLE IF NOT EXISTS signal_calculations (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
    
    -- Signal identification
    signal_id VARCHAR(50) NOT NULL,
    signal_value BOOLEAN NOT NULL,
    signal_strength DECIMAL(4,3) CHECK (signal_strength >= 0 AND signal_strength <= 1),
    
    -- Signal metadata
    threshold_used DECIMAL(10,4),
    actual_value DECIMAL(15,6),
    rolling_median DECIMAL(15,6),
    rolling_std DECIMAL(15,6),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(timestamp, asset, timeframe, signal_id)
);

-- Create hypertable
SELECT create_hypertable('signal_calculations', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_signal_calculations_lookup 
ON signal_calculations (asset, timeframe, signal_id, timestamp DESC);

-- =====================================================
-- Signal Verification Logs (Verification results)
-- =====================================================
CREATE TABLE IF NOT EXISTS signal_verification_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
    
    -- Verification details
    test_name VARCHAR(100) NOT NULL,
    verification_passed BOOLEAN NOT NULL,
    verification_score DECIMAL(4,3) CHECK (verification_score >= 0 AND verification_score <= 1),
    
    -- Test results
    expected_result JSONB,
    actual_result JSONB,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create hypertable
SELECT create_hypertable('signal_verification_logs', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_verification_logs_lookup 
ON signal_verification_logs (asset, timeframe, test_name, timestamp DESC);

-- =====================================================
-- Signal Anomalies Table (Anomaly detection results)
-- =====================================================
CREATE TABLE IF NOT EXISTS signal_anomalies (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    
    -- Anomaly details
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    
    -- Anomaly data
    detected_value DECIMAL(15,6),
    expected_range_min DECIMAL(15,6),
    expected_range_max DECIMAL(15,6),
    confidence DECIMAL(4,3) CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Resolution
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create hypertable
SELECT create_hypertable('signal_anomalies', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_signal_anomalies_unresolved 
ON signal_anomalies (asset, resolved, timestamp DESC) WHERE NOT resolved;

-- =====================================================
-- Audit Calculations Table (Audit trail)
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_calculations (
    id BIGSERIAL PRIMARY KEY,
    calculation_hash VARCHAR(64) NOT NULL UNIQUE,
    
    -- Calculation details
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Audit data
    input_data_hash VARCHAR(64) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    output_data JSONB NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_audit_calculations_lookup 
ON audit_calculations (asset, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_calculations_hash 
ON audit_calculations (calculation_hash);

-- =====================================================
-- Views for easier querying
-- =====================================================

-- Latest OnChain scores view
CREATE OR REPLACE VIEW latest_onchain_scores AS
SELECT DISTINCT ON (asset, timeframe) 
    asset, timeframe, timestamp, onchain_score, confidence, bias,
    network_health_score, capital_flow_score, smart_money_score, risk_penalty,
    data_completeness, conflicting_signals
FROM onchain_scores 
ORDER BY asset, timeframe, timestamp DESC;

-- Latest signals view
CREATE OR REPLACE VIEW latest_signals AS
SELECT DISTINCT ON (asset, timeframe, signal_id)
    asset, timeframe, signal_id, signal_value, signal_strength, timestamp
FROM signal_calculations
ORDER BY asset, timeframe, signal_id, timestamp DESC;

-- Active anomalies view
CREATE OR REPLACE VIEW active_anomalies AS
SELECT asset, anomaly_type, severity, description, timestamp, created_at
FROM signal_anomalies 
WHERE NOT resolved 
ORDER BY severity DESC, created_at DESC;

-- =====================================================
-- Data retention policies
-- =====================================================

-- Keep detailed data for 1 year, aggregated data for 5 years
SELECT add_retention_policy('onchain_scores', INTERVAL '5 years', if_not_exists => TRUE);
SELECT add_retention_policy('signal_calculations', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('signal_verification_logs', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('signal_anomalies', INTERVAL '2 years', if_not_exists => TRUE);
SELECT add_retention_policy('audit_calculations', INTERVAL '7 years', if_not_exists => TRUE);

-- =====================================================
-- Sample data for testing (optional)
-- =====================================================

-- Insert sample OnChain score
INSERT INTO onchain_scores (
    timestamp, asset, timeframe, onchain_score, confidence, bias,
    network_health_score, capital_flow_score, smart_money_score, risk_penalty,
    signal_count, active_signals, conflicting_signals, data_completeness,
    calculation_time_ms, input_data_hash, calculation_hash
) VALUES (
    NOW() - INTERVAL '1 hour', 'BTC', '1d', 72.45, 0.823, 'positive',
    25.37, 24.37, 34.27, 11.56,
    8, 6, 0, 0.96,
    456, 'abc123def456', 'xyz789abc123'
) ON CONFLICT (timestamp, asset, timeframe) DO NOTHING;

-- Insert sample signals
INSERT INTO signal_calculations (
    timestamp, asset, timeframe, signal_id, signal_value, signal_strength,
    threshold_used, actual_value, rolling_median
) VALUES 
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'smart_money_accumulation_signal', TRUE, 0.85, 0.7, 0.89, 0.65),
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'whale_flow_dominance_signal', FALSE, 0.45, 0.6, 0.42, 0.58),
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'network_growth_signal', TRUE, 0.78, 0.5, 0.82, 0.48),
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'smart_money_distribution_signal', FALSE, 0.32, 0.7, 0.28, 0.75)
ON CONFLICT (timestamp, asset, timeframe, signal_id) DO NOTHING;

-- Insert sample verification logs
INSERT INTO signal_verification_logs (
    timestamp, asset, timeframe, test_name, verification_passed, verification_score,
    actual_result
) VALUES 
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'invariant_score_range_test', TRUE, 1.0, '{"min": 0, "max": 100, "actual": 72.45}'),
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'determinism_test', TRUE, 1.0, '{"hash_match": true}'),
    (NOW() - INTERVAL '1 hour', 'BTC', '1d', 'stability_test', TRUE, 0.89, '{"stability_score": 0.89}')
ON CONFLICT DO NOTHING;

-- Grant permissions to onchain_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO onchain_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO onchain_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO onchain_user;

-- Grant TimescaleDB specific permissions
GRANT USAGE ON SCHEMA _timescaledb_catalog TO onchain_user;
GRANT SELECT ON ALL TABLES IN SCHEMA _timescaledb_catalog TO onchain_user;

COMMIT;