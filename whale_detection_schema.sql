-- Bitcoin Whale Detection Engine - Database Schema
-- Statistical whale detection using dynamic percentile thresholds

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- ============================================================================
-- WHALE THRESHOLD MANAGEMENT
-- ============================================================================

CREATE TABLE whale_thresholds_cache (
    id SERIAL PRIMARY KEY,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    calculation_window_hours INTEGER NOT NULL,
    
    -- Whale classification thresholds (BTC)
    large_tx_threshold_p95 DECIMAL(16,8) NOT NULL,     -- P95: Large transactions
    whale_tx_threshold_p99 DECIMAL(16,8) NOT NULL,     -- P99: Whale transactions
    ultra_whale_threshold_p999 DECIMAL(16,8) NOT NULL, -- P99.9: Ultra-whale
    leviathan_threshold_p9999 DECIMAL(16,8),           -- P99.99: Leviathan (optional)
    
    -- UTXO value thresholds
    whale_utxo_threshold_p99 DECIMAL(16,8) NOT NULL,
    ultra_whale_utxo_threshold_p999 DECIMAL(16,8) NOT NULL,
    
    -- Activity spike thresholds
    whale_count_spike_threshold DECIMAL(10,2) NOT NULL,
    whale_volume_spike_threshold DECIMAL(20,8) NOT NULL,
    
    -- Statistical validation metrics
    threshold_stability_score DECIMAL(6,4) DEFAULT 0,  -- 0-1 scale
    regime_change_detected BOOLEAN DEFAULT FALSE,
    sample_size INTEGER NOT NULL,
    distribution_skewness DECIMAL(8,4),
    distribution_kurtosis DECIMAL(8,4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for whale thresholds
CREATE INDEX idx_whale_thresholds_asset_timeframe_time 
ON whale_thresholds_cache(asset, timeframe, calculation_timestamp DESC);

CREATE INDEX idx_whale_thresholds_latest 
ON whale_thresholds_cache(asset, timeframe, calculation_timestamp DESC) 
WHERE calculation_timestamp >= NOW() - INTERVAL '24 hours';

-- ============================================================================
-- 1. WHALE TRANSACTION TIME SERIES
-- ============================================================================

CREATE TABLE whale_tx_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Whale transaction counts by tier
    large_tx_count INTEGER NOT NULL DEFAULT 0,         -- P95+ transactions
    whale_tx_count INTEGER NOT NULL DEFAULT 0,         -- P99+ transactions  
    ultra_whale_tx_count INTEGER DEFAULT 0,            -- P99.9+ transactions
    leviathan_tx_count INTEGER DEFAULT 0,              -- P99.99+ transactions
    
    -- Whale transaction volumes (BTC)
    large_tx_volume_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    whale_tx_volume_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    ultra_whale_tx_volume_btc DECIMAL(20,8) DEFAULT 0,
    leviathan_tx_volume_btc DECIMAL(20,8) DEFAULT 0,
    
    -- Whale transaction ratios (vs total activity)
    whale_tx_ratio DECIMAL(8,6) NOT NULL DEFAULT 0,    -- whale_count / total_count
    whale_volume_ratio DECIMAL(8,6) NOT NULL DEFAULT 0, -- whale_volume / total_volume
    
    -- Statistical metrics
    avg_whale_tx_size_btc DECIMAL(16,8) DEFAULT 0,
    max_whale_tx_size_btc DECIMAL(16,8) DEFAULT 0,
    whale_tx_median_btc DECIMAL(16,8) DEFAULT 0,
    
    -- Threshold metadata (for reference)
    whale_threshold_used_btc DECIMAL(16,8) NOT NULL,
    ultra_whale_threshold_used_btc DECIMAL(16,8),
    
    -- Total context for ratios
    total_tx_count INTEGER NOT NULL,
    total_tx_volume_btc DECIMAL(20,8) NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('whale_tx_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for whale transaction queries
CREATE INDEX idx_whale_tx_ts_asset_timeframe_time 
ON whale_tx_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_whale_tx_ts_whale_count 
ON whale_tx_ts(whale_tx_count DESC, timestamp DESC);

CREATE INDEX idx_whale_tx_ts_whale_volume 
ON whale_tx_ts(whale_tx_volume_btc DESC, timestamp DESC);

CREATE INDEX idx_whale_tx_ts_whale_ratio 
ON whale_tx_ts(whale_volume_ratio DESC, timestamp DESC);

-- ============================================================================
-- 2. WHALE UTXO FLOW TIME SERIES  
-- ============================================================================

CREATE TABLE whale_utxo_flow_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Whale UTXO creation (potential accumulation)
    whale_utxo_created_count INTEGER NOT NULL DEFAULT 0,
    whale_utxo_created_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    ultra_whale_utxo_created_count INTEGER DEFAULT 0,
    ultra_whale_utxo_created_btc DECIMAL(20,8) DEFAULT 0,
    
    -- Whale UTXO spending (potential distribution)  
    whale_utxo_spent_count INTEGER NOT NULL DEFAULT 0,
    whale_utxo_spent_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    ultra_whale_utxo_spent_count INTEGER DEFAULT 0,
    ultra_whale_utxo_spent_btc DECIMAL(20,8) DEFAULT 0,
    
    -- Net whale flow (created - spent)
    whale_net_flow_btc DECIMAL(20,8) NOT NULL DEFAULT 0,
    ultra_whale_net_flow_btc DECIMAL(20,8) DEFAULT 0,
    
    -- Whale UTXO characteristics
    avg_whale_utxo_age_days DECIMAL(10,2) DEFAULT 0,
    median_whale_utxo_age_days DECIMAL(10,2) DEFAULT 0,
    whale_utxo_age_weighted_avg DECIMAL(10,2) DEFAULT 0, -- Value-weighted average age
    
    -- Whale vs total UTXO ratios
    whale_utxo_creation_ratio DECIMAL(8,6) DEFAULT 0,   -- whale_created / total_created
    whale_utxo_spending_ratio DECIMAL(8,6) DEFAULT 0,   -- whale_spent / total_spent
    
    -- Coinbase whale UTXOs (mining-related)
    whale_coinbase_utxo_count INTEGER DEFAULT 0,
    whale_coinbase_utxo_btc DECIMAL(16,8) DEFAULT 0,
    
    -- Threshold metadata
    whale_utxo_threshold_used_btc DECIMAL(16,8) NOT NULL,
    ultra_whale_utxo_threshold_used_btc DECIMAL(16,8),
    
    -- Total context for ratios
    total_utxo_created_count INTEGER NOT NULL,
    total_utxo_created_btc DECIMAL(20,8) NOT NULL,
    total_utxo_spent_count INTEGER NOT NULL,
    total_utxo_spent_btc DECIMAL(20,8) NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('whale_utxo_flow_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for whale UTXO flow queries
CREATE INDEX idx_whale_utxo_flow_ts_asset_timeframe_time 
ON whale_utxo_flow_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_whale_utxo_flow_ts_net_flow 
ON whale_utxo_flow_ts(whale_net_flow_btc DESC, timestamp DESC);

CREATE INDEX idx_whale_utxo_flow_ts_creation_ratio 
ON whale_utxo_flow_ts(whale_utxo_creation_ratio DESC, timestamp DESC);

-- ============================================================================
-- 3. WHALE BEHAVIOR FLAGS TIME SERIES
-- ============================================================================

CREATE TABLE whale_behavior_flags_ts (
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    
    -- Primary behavior flags (boolean indicators)
    accumulation_flag BOOLEAN NOT NULL DEFAULT FALSE,
    distribution_flag BOOLEAN NOT NULL DEFAULT FALSE,
    activity_spike_flag BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Secondary behavior flags
    ultra_whale_accumulation_flag BOOLEAN DEFAULT FALSE,
    ultra_whale_distribution_flag BOOLEAN DEFAULT FALSE,
    whale_dormancy_break_flag BOOLEAN DEFAULT FALSE,    -- Old whale UTXOs moving
    
    -- Behavioral strength indicators (0-1 scale)
    accumulation_strength DECIMAL(6,4) DEFAULT 0,       -- How strong the accumulation
    distribution_strength DECIMAL(6,4) DEFAULT 0,       -- How strong the distribution  
    activity_spike_strength DECIMAL(6,4) DEFAULT 0,     -- How strong the spike
    
    -- Statistical context for flags
    whale_count_zscore DECIMAL(8,4) DEFAULT 0,          -- Z-score vs historical
    whale_volume_zscore DECIMAL(8,4) DEFAULT 0,
    whale_ratio_zscore DECIMAL(8,4) DEFAULT 0,
    
    -- Trend analysis (over recent periods)
    whale_count_trend_7p DECIMAL(6,4) DEFAULT 0,        -- 7-period trend strength
    whale_volume_trend_7p DECIMAL(6,4) DEFAULT 0,
    whale_ratio_trend_7p DECIMAL(6,4) DEFAULT 0,
    
    -- Pattern persistence (how many consecutive periods)
    accumulation_streak INTEGER DEFAULT 0,
    distribution_streak INTEGER DEFAULT 0,
    activity_spike_streak INTEGER DEFAULT 0,
    
    -- Confidence metrics
    flag_confidence_score DECIMAL(6,4) DEFAULT 0,       -- Overall confidence in flags
    data_quality_score DECIMAL(6,4) DEFAULT 1,          -- Data completeness/quality
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('whale_behavior_flags_ts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for whale behavior flags
CREATE INDEX idx_whale_behavior_flags_ts_asset_timeframe_time 
ON whale_behavior_flags_ts(asset, timeframe, timestamp DESC);

CREATE INDEX idx_whale_behavior_flags_ts_accumulation 
ON whale_behavior_flags_ts(timestamp DESC) 
WHERE accumulation_flag = TRUE;

CREATE INDEX idx_whale_behavior_flags_ts_distribution 
ON whale_behavior_flags_ts(timestamp DESC) 
WHERE distribution_flag = TRUE;

CREATE INDEX idx_whale_behavior_flags_ts_activity_spike 
ON whale_behavior_flags_ts(timestamp DESC) 
WHERE activity_spike_flag = TRUE;

CREATE INDEX idx_whale_behavior_flags_ts_strength 
ON whale_behavior_flags_ts(accumulation_strength DESC, distribution_strength DESC, timestamp DESC);

-- ============================================================================
-- WHALE DETECTION STATE MANAGEMENT
-- ============================================================================

CREATE TABLE whale_detection_state (
    id SERIAL PRIMARY KEY,
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    last_processed_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    last_threshold_calculation TIMESTAMP WITH TIME ZONE,
    is_processing BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint per asset-timeframe
CREATE UNIQUE INDEX idx_whale_detection_state_asset_timeframe 
ON whale_detection_state(asset, timeframe);

-- ============================================================================
-- VIEWS FOR COMMON WHALE QUERIES
-- ============================================================================

-- Latest whale activity across timeframes
CREATE VIEW latest_whale_activity AS
SELECT 
    w.timeframe,
    w.timestamp,
    w.whale_tx_count,
    w.whale_tx_volume_btc,
    w.whale_volume_ratio,
    f.accumulation_flag,
    f.distribution_flag,
    f.activity_spike_flag,
    u.whale_net_flow_btc
FROM whale_tx_ts w
LEFT JOIN whale_behavior_flags_ts f ON (
    w.timestamp = f.timestamp AND 
    w.asset = f.asset AND 
    w.timeframe = f.timeframe
)
LEFT JOIN whale_utxo_flow_ts u ON (
    w.timestamp = u.timestamp AND 
    w.asset = u.asset AND 
    w.timeframe = u.timeframe
)
WHERE w.asset = 'BTC'
    AND w.timestamp >= NOW() - INTERVAL '7 days'
ORDER BY w.timeframe, w.timestamp DESC;

-- Whale accumulation periods
CREATE VIEW whale_accumulation_periods AS
SELECT 
    timeframe,
    timestamp,
    accumulation_strength,
    accumulation_streak,
    whale_net_flow_btc,
    whale_volume_ratio
FROM whale_behavior_flags_ts f
JOIN whale_utxo_flow_ts u USING (timestamp, asset, timeframe)
WHERE asset = 'BTC'
    AND accumulation_flag = TRUE
    AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timeframe, timestamp DESC;

-- Whale distribution periods  
CREATE VIEW whale_distribution_periods AS
SELECT 
    timeframe,
    timestamp,
    distribution_strength,
    distribution_streak,
    whale_net_flow_btc,
    whale_volume_ratio
FROM whale_behavior_flags_ts f
JOIN whale_utxo_flow_ts u USING (timestamp, asset, timeframe)
WHERE asset = 'BTC'
    AND distribution_flag = TRUE
    AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timeframe, timestamp DESC;

-- Whale activity spikes
CREATE VIEW whale_activity_spikes AS
SELECT 
    timeframe,
    timestamp,
    whale_tx_count,
    whale_tx_volume_btc,
    activity_spike_strength,
    whale_count_zscore,
    whale_volume_zscore
FROM whale_tx_ts w
JOIN whale_behavior_flags_ts f USING (timestamp, asset, timeframe)
WHERE asset = 'BTC'
    AND activity_spike_flag = TRUE
    AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY activity_spike_strength DESC, timestamp DESC;

-- ============================================================================
-- TRIGGERS FOR DATA CONSISTENCY
-- ============================================================================

-- Update whale detection state timestamp
CREATE OR REPLACE FUNCTION update_whale_detection_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_whale_detection_state_updated_at
    BEFORE UPDATE ON whale_detection_state
    FOR EACH ROW
    EXECUTE FUNCTION update_whale_detection_state_timestamp();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Initialize whale detection state for different timeframes
INSERT INTO whale_detection_state (asset, timeframe, last_processed_timestamp) 
VALUES 
    ('BTC', '1h', '1970-01-01 00:00:00+00'),
    ('BTC', '4h', '1970-01-01 00:00:00+00'),
    ('BTC', '1d', '1970-01-01 00:00:00+00')
ON CONFLICT (asset, timeframe) DO NOTHING;

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Compression for historical whale data
ALTER TABLE whale_tx_ts SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset,timeframe'
);

ALTER TABLE whale_utxo_flow_ts SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset,timeframe'
);

ALTER TABLE whale_behavior_flags_ts SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset,timeframe'
);

-- Continuous aggregates for whale metrics
CREATE MATERIALIZED VIEW whale_daily_summary
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', timestamp) AS day,
       asset,
       AVG(whale_tx_count) as avg_whale_tx_count,
       SUM(whale_tx_volume_btc) as total_whale_volume,
       AVG(whale_volume_ratio) as avg_whale_ratio,
       COUNT(CASE WHEN accumulation_flag THEN 1 END) as accumulation_periods,
       COUNT(CASE WHEN distribution_flag THEN 1 END) as distribution_periods,
       COUNT(CASE WHEN activity_spike_flag THEN 1 END) as spike_periods
FROM whale_tx_ts w
LEFT JOIN whale_behavior_flags_ts f USING (timestamp, asset, timeframe)
WHERE timeframe = '1h'  -- Use hourly data for daily aggregation
GROUP BY day, asset;

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE whale_thresholds_cache IS 'Cached whale detection thresholds with statistical validation';
COMMENT ON TABLE whale_tx_ts IS 'Time-series whale transaction activity metrics';
COMMENT ON TABLE whale_utxo_flow_ts IS 'Time-series whale UTXO creation and spending flows';
COMMENT ON TABLE whale_behavior_flags_ts IS 'Time-series whale behavioral pattern flags';

COMMENT ON COLUMN whale_tx_ts.whale_tx_ratio IS 'Ratio of whale transactions to total transactions';
COMMENT ON COLUMN whale_utxo_flow_ts.whale_net_flow_btc IS 'Net whale UTXO flow (created - spent)';
COMMENT ON COLUMN whale_behavior_flags_ts.accumulation_flag IS 'Boolean flag indicating whale accumulation pattern';
COMMENT ON COLUMN whale_behavior_flags_ts.distribution_flag IS 'Boolean flag indicating whale distribution pattern';
COMMENT ON COLUMN whale_behavior_flags_ts.activity_spike_flag IS 'Boolean flag indicating whale activity spike';