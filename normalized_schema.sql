-- Bitcoin Normalization Layer - Time-Series Schema
-- Transforms raw UTXO data into statistical time-series features

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- ============================================================================
-- NORMALIZATION STATE MANAGEMENT
-- ============================================================================

CREATE TABLE normalization_state (
    id SERIAL PRIMARY KEY,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL, -- '1h', '4h', '1d'
    last_normalized_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    last_processed_block_height BIGINT NOT NULL,
    normalization_started_at TIMESTAMP WITH TIME ZONE,
    normalization_completed_at TIMESTAMP WITH TIME ZONE,
    is_normalizing BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint per asset-timeframe combination
CREATE UNIQUE INDEX idx_normalization_state_asset_timeframe 
ON normalization_state(asset, timeframe);

-- ============================================================================
-- A. NETWORK ACTIVITY TIME SERIES
-- ============================================================================

CREATE TABLE network_activity_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Core network metrics
    active_addresses INTEGER NOT NULL DEFAULT 0,
    tx_count INTEGER NOT NULL DEFAULT 0,
    total_tx_volume_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    avg_tx_value_btc DECIMAL(16,8) NOT NULL DEFAULT 0,
    
    -- Additional network statistics
    median_tx_value_btc DECIMAL(16,8) DEFAULT 0,
    total_fees_btc DECIMAL(16,8) DEFAULT 0,
    avg_fee_per_tx_btc DECIMAL(16,8) DEFAULT 0,
    avg_tx_size_bytes DECIMAL(10,2) DEFAULT 0,
    
    -- Block-level aggregations
    blocks_mined INTEGER DEFAULT 0,
    avg_block_size_bytes DECIMAL(12,2) DEFAULT 0,
    avg_tx_per_block DECIMAL(8,2) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('network_activity_ts', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for network activity queries
CREATE INDEX idx_network_activity_ts_asset_timeframe_time 
ON network_activity_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_network_activity_ts_active_addresses 
ON network_activity_ts(active_addresses DESC, timestamp DESC);

CREATE INDEX idx_network_activity_ts_volume 
ON network_activity_ts(total_tx_volume_btc DESC, timestamp DESC);

-- ============================================================================
-- B. UTXO FLOW TIME SERIES
-- ============================================================================

CREATE TABLE utxo_flow_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- UTXO creation/destruction
    utxo_created_count INTEGER NOT NULL DEFAULT 0,
    utxo_spent_count INTEGER NOT NULL DEFAULT 0,
    net_utxo_change INTEGER NOT NULL DEFAULT 0, -- created - spent
    
    -- BTC flow analysis
    btc_created DECIMAL(20,8) NOT NULL DEFAULT 0,
    btc_spent DECIMAL(20,8) NOT NULL DEFAULT 0,
    net_utxo_flow_btc DECIMAL(20,8) NOT NULL DEFAULT 0, -- created - spent
    
    -- UTXO size distribution
    utxo_created_avg_value_btc DECIMAL(16,8) DEFAULT 0,
    utxo_spent_avg_value_btc DECIMAL(16,8) DEFAULT 0,
    
    -- UTXO age analysis
    avg_utxo_age_days DECIMAL(10,2) DEFAULT 0,
    median_utxo_age_days DECIMAL(10,2) DEFAULT 0,
    
    -- Coinbase vs regular UTXOs
    coinbase_utxo_created_count INTEGER DEFAULT 0,
    coinbase_btc_created DECIMAL(16,8) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('utxo_flow_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for UTXO flow queries
CREATE INDEX idx_utxo_flow_ts_asset_timeframe_time 
ON utxo_flow_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_utxo_flow_ts_net_flow 
ON utxo_flow_ts(net_utxo_flow_btc DESC, timestamp DESC);

CREATE INDEX idx_utxo_flow_ts_creation_rate 
ON utxo_flow_ts(utxo_created_count DESC, timestamp DESC);

-- ============================================================================
-- C. ADDRESS BEHAVIOR TIME SERIES
-- ============================================================================

CREATE TABLE address_behavior_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Address lifecycle metrics
    new_addresses INTEGER NOT NULL DEFAULT 0,
    dormant_addresses_activated INTEGER NOT NULL DEFAULT 0,
    addresses_with_outflows INTEGER DEFAULT 0,
    addresses_with_inflows INTEGER DEFAULT 0,
    
    -- Address activity patterns
    address_churn_rate DECIMAL(8,6) DEFAULT 0, -- (new + reactivated) / total_active
    address_reuse_rate DECIMAL(8,6) DEFAULT 0, -- existing_active / total_active
    
    -- Address balance distribution changes
    addresses_balance_increased INTEGER DEFAULT 0,
    addresses_balance_decreased INTEGER DEFAULT 0,
    addresses_emptied INTEGER DEFAULT 0, -- balance went to 0
    
    -- Dormancy analysis (addresses inactive for 30+ days)
    dormancy_threshold_days INTEGER DEFAULT 30,
    total_dormant_addresses INTEGER DEFAULT 0,
    dormant_btc_activated DECIMAL(20,8) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('address_behavior_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for address behavior queries
CREATE INDEX idx_address_behavior_ts_asset_timeframe_time 
ON address_behavior_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_address_behavior_ts_new_addresses 
ON address_behavior_ts(new_addresses DESC, timestamp DESC);

CREATE INDEX idx_address_behavior_ts_churn_rate 
ON address_behavior_ts(address_churn_rate DESC, timestamp DESC);

-- ============================================================================
-- D. VALUE DISTRIBUTION TIME SERIES
-- ============================================================================

CREATE TABLE value_distribution_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Transaction value percentiles (BTC)
    tx_value_p10 DECIMAL(16,8) DEFAULT 0,
    tx_value_p25 DECIMAL(16,8) DEFAULT 0,
    tx_value_p50 DECIMAL(16,8) DEFAULT 0, -- median
    tx_value_p75 DECIMAL(16,8) DEFAULT 0,
    tx_value_p90 DECIMAL(16,8) DEFAULT 0,
    tx_value_p95 DECIMAL(16,8) DEFAULT 0,
    tx_value_p99 DECIMAL(16,8) DEFAULT 0,
    tx_value_p999 DECIMAL(16,8) DEFAULT 0, -- 99.9th percentile
    
    -- UTXO value percentiles (BTC)
    utxo_value_p10 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p25 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p50 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p75 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p90 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p95 DECIMAL(16,8) DEFAULT 0,
    utxo_value_p99 DECIMAL(16,8) DEFAULT 0,
    
    -- Fee distribution percentiles (BTC)
    fee_p10 DECIMAL(16,8) DEFAULT 0,
    fee_p50 DECIMAL(16,8) DEFAULT 0,
    fee_p90 DECIMAL(16,8) DEFAULT 0,
    fee_p99 DECIMAL(16,8) DEFAULT 0,
    
    -- Distribution statistics
    tx_value_gini_coefficient DECIMAL(8,6) DEFAULT 0, -- wealth inequality measure
    tx_value_std_dev DECIMAL(16,8) DEFAULT 0,
    tx_value_skewness DECIMAL(10,6) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('value_distribution_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for value distribution queries
CREATE INDEX idx_value_distribution_ts_asset_timeframe_time 
ON value_distribution_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_value_distribution_ts_p99 
ON value_distribution_ts(tx_value_p99 DESC, timestamp DESC);

-- ============================================================================
-- E. LARGE TRANSACTION ACTIVITY TIME SERIES
-- ============================================================================

CREATE TABLE large_tx_activity_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Large transaction metrics (based on rolling percentiles)
    large_tx_threshold_btc DECIMAL(16,8) NOT NULL, -- Dynamic threshold (e.g., P95)
    large_tx_count INTEGER NOT NULL DEFAULT 0,
    large_tx_volume_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    large_tx_ratio DECIMAL(8,6) NOT NULL DEFAULT 0, -- large_tx_count / total_tx_count
    large_tx_volume_ratio DECIMAL(8,6) DEFAULT 0, -- large_volume / total_volume
    
    -- Whale activity indicators
    whale_tx_threshold_btc DECIMAL(16,8) NOT NULL, -- Ultra-large (e.g., P99.9)
    whale_tx_count INTEGER DEFAULT 0,
    whale_tx_volume_btc DECIMAL(20,8) DEFAULT 0,
    whale_tx_ratio DECIMAL(8,6) DEFAULT 0,
    
    -- Large transaction characteristics
    avg_large_tx_value_btc DECIMAL(16,8) DEFAULT 0,
    max_tx_value_btc DECIMAL(16,8) DEFAULT 0,
    large_tx_avg_fee_btc DECIMAL(16,8) DEFAULT 0,
    
    -- Exchange-related large transactions (heuristic-based)
    potential_exchange_large_tx_count INTEGER DEFAULT 0,
    potential_exchange_large_tx_volume_btc DECIMAL(20,8) DEFAULT 0,
    
    -- Threshold calculation metadata
    threshold_calculation_window_hours INTEGER DEFAULT 720, -- 30 days
    threshold_percentile DECIMAL(5,2) DEFAULT 95.0, -- P95 for "large"
    whale_threshold_percentile DECIMAL(5,2) DEFAULT 99.9, -- P99.9 for "whale"
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('large_tx_activity_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for large transaction queries
CREATE INDEX idx_large_tx_activity_ts_asset_timeframe_time 
ON large_tx_activity_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_large_tx_activity_ts_count 
ON large_tx_activity_ts(large_tx_count DESC, timestamp DESC);

CREATE INDEX idx_large_tx_activity_ts_volume 
ON large_tx_activity_ts(large_tx_volume_btc DESC, timestamp DESC);

CREATE INDEX idx_large_tx_activity_ts_whale_activity 
ON large_tx_activity_ts(whale_tx_count DESC, timestamp DESC);

-- ============================================================================
-- STATISTICAL THRESHOLD CACHE
-- ============================================================================

-- Cache for rolling percentile calculations to improve performance
CREATE TABLE statistical_thresholds_cache (
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    window_hours INTEGER NOT NULL,
    
    -- Transaction value percentiles
    tx_value_p50 DECIMAL(16,8),
    tx_value_p75 DECIMAL(16,8),
    tx_value_p90 DECIMAL(16,8),
    tx_value_p95 DECIMAL(16,8),
    tx_value_p99 DECIMAL(16,8),
    tx_value_p999 DECIMAL(16,8),
    
    -- UTXO value percentiles
    utxo_value_p95 DECIMAL(16,8),
    utxo_value_p99 DECIMAL(16,8),
    
    -- Fee percentiles
    fee_p95 DECIMAL(16,8),
    fee_p99 DECIMAL(16,8),
    
    -- Sample size for validation
    tx_sample_size INTEGER,
    utxo_sample_size INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for threshold cache
CREATE INDEX idx_statistical_thresholds_cache_asset_time 
ON statistical_thresholds_cache(asset, calculation_timestamp DESC);

CREATE INDEX idx_statistical_thresholds_cache_window 
ON statistical_thresholds_cache(window_hours, calculation_timestamp DESC);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest normalized data across all timeframes
CREATE VIEW latest_network_metrics AS
SELECT 
    timeframe,
    timestamp,
    active_addresses,
    tx_count,
    total_tx_volume_btc,
    avg_tx_value_btc
FROM network_activity_ts 
WHERE asset = 'BTC'
    AND timestamp >= NOW() - INTERVAL '7 days'
ORDER BY timeframe, timestamp DESC;

-- Large transaction activity summary
CREATE VIEW large_tx_summary AS
SELECT 
    timeframe,
    timestamp,
    large_tx_count,
    large_tx_volume_btc,
    large_tx_ratio,
    whale_tx_count,
    whale_tx_volume_btc,
    large_tx_threshold_btc
FROM large_tx_activity_ts
WHERE asset = 'BTC'
    AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timeframe, timestamp DESC;

-- Address behavior trends
CREATE VIEW address_behavior_trends AS
SELECT 
    timeframe,
    timestamp,
    new_addresses,
    dormant_addresses_activated,
    address_churn_rate,
    dormant_btc_activated
FROM address_behavior_ts
WHERE asset = 'BTC'
    AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timeframe, timestamp DESC;

-- ============================================================================
-- TRIGGERS FOR DATA CONSISTENCY
-- ============================================================================

-- Update normalization state timestamp on changes
CREATE OR REPLACE FUNCTION update_normalization_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_normalization_state_updated_at
    BEFORE UPDATE ON normalization_state
    FOR EACH ROW
    EXECUTE FUNCTION update_normalization_state_timestamp();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Initialize normalization state for different timeframes
INSERT INTO normalization_state (asset, timeframe, last_normalized_timestamp, last_processed_block_height) 
VALUES 
    ('BTC', '1h', '1970-01-01 00:00:00+00', 0),
    ('BTC', '4h', '1970-01-01 00:00:00+00', 0),
    ('BTC', '1d', '1970-01-01 00:00:00+00', 0)
ON CONFLICT (asset, timeframe) DO NOTHING;

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE network_activity_ts IS 'Time-series network activity metrics aggregated by timeframe';
COMMENT ON TABLE utxo_flow_ts IS 'UTXO creation/spending flow analysis over time';
COMMENT ON TABLE address_behavior_ts IS 'Address lifecycle and behavioral patterns';
COMMENT ON TABLE value_distribution_ts IS 'Statistical distribution of transaction and UTXO values';
COMMENT ON TABLE large_tx_activity_ts IS 'Large transaction activity with dynamic thresholds';
COMMENT ON TABLE statistical_thresholds_cache IS 'Cached percentile calculations for performance';

COMMENT ON COLUMN large_tx_activity_ts.large_tx_threshold_btc IS 'Dynamic threshold based on rolling percentiles (typically P95)';
COMMENT ON COLUMN large_tx_activity_ts.whale_tx_threshold_btc IS 'Ultra-large transaction threshold (typically P99.9)';
COMMENT ON COLUMN address_behavior_ts.address_churn_rate IS 'Rate of new and reactivated addresses relative to total active';
COMMENT ON COLUMN value_distribution_ts.tx_value_gini_coefficient IS 'Gini coefficient measuring transaction value inequality';