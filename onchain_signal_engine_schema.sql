-- OnChain Signal & Score Engine - Database Schema
-- Production-grade signal storage and verification system

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ============================================================================
-- SIGNAL DEFINITIONS & METADATA
-- ============================================================================

CREATE TABLE signal_definitions (
    signal_id VARCHAR(50) PRIMARY KEY,
    signal_name VARCHAR(100) NOT NULL,
    signal_category VARCHAR(30) NOT NULL, -- 'network_health', 'capital_flow', 'smart_money', 'risk'
    signal_type VARCHAR(20) NOT NULL, -- 'binary', 'categorical', 'intensity'
    description TEXT NOT NULL,
    
    -- Mathematical definition
    calculation_logic TEXT NOT NULL,
    threshold_parameters JSONB NOT NULL,
    baseline_lookback_periods INTEGER DEFAULT 30,
    
    -- Component assignment
    component_name VARCHAR(30) NOT NULL,
    component_weight DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1
);

-- Insert signal definitions
INSERT INTO signal_definitions (signal_id, signal_name, signal_category, signal_type, description, calculation_logic, threshold_parameters, component_name, component_weight) VALUES
('network_growth_signal', 'Network Growth Signal', 'network_health', 'binary', 'Detects sustained network growth across multiple metrics', 'active_addresses_growth > P75 AND tx_count_growth > P75 AND new_addresses_growth > P75', '{"active_addresses_threshold_percentile": 75, "tx_count_threshold_percentile": 75, "new_addresses_threshold_percentile": 75}', 'network_health', 0.5000),
('network_congestion_signal', 'Network Congestion Signal', 'network_health', 'binary', 'Detects network congestion through transaction patterns', 'avg_fee > P90 AND confirmation_time > P90 AND mempool_size > P85 (2 of 3)', '{"fee_threshold_percentile": 90, "time_threshold_percentile": 90, "mempool_threshold_percentile": 85}', 'network_health', 0.5000),
('net_utxo_inflow_signal', 'Net UTXO Inflow Signal', 'capital_flow', 'binary', 'Detects sustained net UTXO inflow (accumulation)', 'net_flow > 0 AND 7d_avg > P70 AND creation_rate > 1.1', '{"flow_threshold_percentile": 70, "creation_rate_threshold": 1.1}', 'capital_flow', 0.5000),
('whale_flow_dominance_signal', 'Whale Flow Dominance Signal', 'capital_flow', 'binary', 'Detects when whale activity dominates network flow', 'whale_volume_ratio > 0.4 AND whale_count_ratio > 0.15', '{"volume_dominance_threshold": 0.4, "count_dominance_threshold": 0.15}', 'capital_flow', 0.5000),
('smart_money_accumulation_signal', 'Smart Money Accumulation Signal', 'smart_money', 'binary', 'Detects smart money accumulation behavior', 'smart_net_accumulation > P60 AND smart_volume_growth > P70 (2 of 3)', '{"accumulation_threshold_percentile": 60, "volume_threshold_percentile": 70, "address_threshold_percentile": 65}', 'smart_money', 0.5000),
('smart_money_distribution_signal', 'Smart Money Distribution Signal', 'smart_money', 'binary', 'Detects smart money distribution behavior', 'smart_net_flow < P40 AND smart_spending_rate > P75 (2 of 3)', '{"flow_threshold_percentile": 40, "spending_threshold_percentile": 75, "holding_threshold_percentile": 30}', 'smart_money', 0.5000),
('abnormal_activity_signal', 'Abnormal Activity Signal', 'risk', 'binary', 'Detects abnormal network activity patterns', 'any_metric < P5 OR any_metric > P95 OR z_score > 3.0', '{"lower_percentile": 5, "upper_percentile": 95, "zscore_threshold": 3.0}', 'risk_adjustment', 1.0000),
('capital_concentration_signal', 'Capital Concentration Signal', 'risk', 'binary', 'Detects excessive capital concentration', 'large_tx_volume_ratio > 0.7 AND whale_count > P90 (2 of 3)', '{"concentration_threshold": 0.7, "whale_count_percentile": 90, "gini_percentile": 85}', 'risk_adjustment', 1.0000);

-- ============================================================================
-- SIGNAL CALCULATION RESULTS
-- ============================================================================

CREATE TABLE signal_calculations (
    calculation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL, -- '1h', '4h', '1d'
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Signal results
    signal_id VARCHAR(50) NOT NULL REFERENCES signal_definitions(signal_id),
    signal_value BOOLEAN NOT NULL, -- For binary signals
    signal_confidence DECIMAL(6,4) NOT NULL CHECK (signal_confidence >= 0 AND signal_confidence <= 1),
    
    -- Calculation metadata
    input_data_hash VARCHAR(64) NOT NULL, -- SHA-256 of input data
    threshold_values JSONB NOT NULL, -- Actual threshold values used
    baseline_metrics JSONB NOT NULL, -- Baseline statistics used
    
    -- Verification data
    calculation_time_ms INTEGER DEFAULT 0,
    data_quality_score DECIMAL(6,4) DEFAULT 1.0000,
    statistical_significance DECIMAL(6,4) DEFAULT 0.0000,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(asset, timeframe, timestamp, signal_id)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('signal_calculations', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for signal calculations
CREATE INDEX idx_signal_calculations_asset_timeframe_time 
ON signal_calculations(asset, timeframe, timestamp DESC);

CREATE INDEX idx_signal_calculations_signal_id_time 
ON signal_calculations(signal_id, timestamp DESC);

CREATE INDEX idx_signal_calculations_confidence 
ON signal_calculations(signal_confidence DESC, timestamp DESC);

-- ============================================================================
-- ONCHAIN SCORE RESULTS
-- ============================================================================

CREATE TABLE onchain_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Core results
    onchain_score DECIMAL(6,2) NOT NULL CHECK (onchain_score >= 0 AND onchain_score <= 100),
    confidence DECIMAL(6,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    bias VARCHAR(10) NOT NULL CHECK (bias IN ('positive', 'neutral', 'negative')),
    
    -- Component breakdown
    network_health_score DECIMAL(6,2) DEFAULT 0.00,
    capital_flow_score DECIMAL(6,2) DEFAULT 0.00,
    smart_money_score DECIMAL(6,2) DEFAULT 0.00,
    risk_penalty DECIMAL(6,2) DEFAULT 0.00,
    
    -- Component confidences
    network_health_confidence DECIMAL(6,4) DEFAULT 0.0000,
    capital_flow_confidence DECIMAL(6,4) DEFAULT 0.0000,
    smart_money_confidence DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Confidence breakdown
    signal_agreement_confidence DECIMAL(6,4) DEFAULT 0.0000,
    historical_stability_confidence DECIMAL(6,4) DEFAULT 0.0000,
    data_quality_confidence DECIMAL(6,4) DEFAULT 0.0000,
    statistical_significance_confidence DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Verification metadata
    input_data_hash VARCHAR(64) NOT NULL,
    calculation_hash VARCHAR(64) NOT NULL,
    signal_count INTEGER DEFAULT 0,
    active_signals INTEGER DEFAULT 0,
    conflicting_signals INTEGER DEFAULT 0,
    
    -- Performance metadata
    calculation_time_ms INTEGER DEFAULT 0,
    data_completeness DECIMAL(6,4) DEFAULT 1.0000,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(asset, timeframe, timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('onchain_scores', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for onchain scores
CREATE INDEX idx_onchain_scores_asset_timeframe_time 
ON onchain_scores(asset, timeframe, timestamp DESC);

CREATE INDEX idx_onchain_scores_score_confidence 
ON onchain_scores(onchain_score DESC, confidence DESC);

CREATE INDEX idx_onchain_scores_bias_time 
ON onchain_scores(bias, timestamp DESC);

-- ============================================================================
-- SIGNAL AGGREGATION SUMMARY
-- ============================================================================

CREATE TABLE signal_summary (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Signal counts by category
    network_health_signals_active INTEGER DEFAULT 0,
    capital_flow_signals_active INTEGER DEFAULT 0,
    smart_money_signals_active INTEGER DEFAULT 0,
    risk_signals_active INTEGER DEFAULT 0,
    
    -- Signal agreement metrics
    bullish_signals_count INTEGER DEFAULT 0,
    bearish_signals_count INTEGER DEFAULT 0,
    neutral_signals_count INTEGER DEFAULT 0,
    conflicting_signals_count INTEGER DEFAULT 0,
    
    -- Confidence metrics
    avg_signal_confidence DECIMAL(6,4) DEFAULT 0.0000,
    min_signal_confidence DECIMAL(6,4) DEFAULT 0.0000,
    max_signal_confidence DECIMAL(6,4) DEFAULT 0.0000,
    confidence_std_dev DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Quality metrics
    data_quality_score DECIMAL(6,4) DEFAULT 1.0000,
    calculation_success_rate DECIMAL(6,4) DEFAULT 1.0000,
    anomaly_flags_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(asset, timeframe, timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('signal_summary', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ============================================================================
-- HISTORICAL BASELINES & THRESHOLDS
-- ============================================================================

CREATE TABLE signal_baselines (
    baseline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    signal_id VARCHAR(50) NOT NULL REFERENCES signal_definitions(signal_id),
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Baseline period
    baseline_start_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    baseline_end_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    baseline_period_days INTEGER NOT NULL,
    
    -- Statistical baselines
    baseline_mean DECIMAL(16,8) DEFAULT 0.00000000,
    baseline_median DECIMAL(16,8) DEFAULT 0.00000000,
    baseline_std_dev DECIMAL(16,8) DEFAULT 0.00000000,
    baseline_min DECIMAL(16,8) DEFAULT 0.00000000,
    baseline_max DECIMAL(16,8) DEFAULT 0.00000000,
    
    -- Percentile thresholds
    p5_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    p10_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    p25_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    p75_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    p90_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    p95_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    
    -- Dynamic thresholds (calculated)
    current_threshold DECIMAL(16,8) DEFAULT 0.00000000,
    threshold_type VARCHAR(20) DEFAULT 'percentile', -- 'percentile', 'zscore', 'iqr'
    
    -- Quality metrics
    sample_size INTEGER DEFAULT 0,
    data_completeness DECIMAL(6,4) DEFAULT 1.0000,
    outlier_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(asset, timeframe, signal_id, calculation_timestamp)
);

-- Index for baselines
CREATE INDEX idx_signal_baselines_signal_time 
ON signal_baselines(signal_id, calculation_timestamp DESC);

-- ============================================================================
-- SIGNAL STABILITY TRACKING
-- ============================================================================

CREATE TABLE signal_stability (
    stability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    signal_id VARCHAR(50) NOT NULL REFERENCES signal_definitions(signal_id),
    analysis_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Stability analysis period
    analysis_start_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    analysis_end_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    analysis_period_days INTEGER NOT NULL,
    
    -- Stability metrics
    signal_flip_count INTEGER DEFAULT 0, -- Number of true/false changes
    signal_stability_ratio DECIMAL(6,4) DEFAULT 1.0000, -- 1 - (flips / total_periods)
    confidence_volatility DECIMAL(6,4) DEFAULT 0.0000, -- Std dev of confidence scores
    avg_confidence DECIMAL(6,4) DEFAULT 0.0000,
    min_confidence DECIMAL(6,4) DEFAULT 0.0000,
    max_confidence DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Trend analysis
    signal_trend VARCHAR(20) DEFAULT 'stable', -- 'increasing', 'decreasing', 'stable', 'volatile'
    confidence_trend VARCHAR(20) DEFAULT 'stable',
    recent_stability_score DECIMAL(6,4) DEFAULT 1.0000, -- Last 7 days stability
    
    -- Classification
    stability_class VARCHAR(20) DEFAULT 'stable', -- 'stable', 'volatile', 'erratic'
    reliability_score DECIMAL(6,4) DEFAULT 1.0000, -- Overall reliability assessment
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(asset, timeframe, signal_id, analysis_timestamp)
);

-- Index for stability tracking
CREATE INDEX idx_signal_stability_signal_time 
ON signal_stability(signal_id, analysis_timestamp DESC);

CREATE INDEX idx_signal_stability_reliability 
ON signal_stability(reliability_score DESC, analysis_timestamp DESC);

-- ============================================================================
-- VERIFICATION & AUDIT LOGS
-- ============================================================================

CREATE TABLE signal_verification_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    verification_type VARCHAR(30) NOT NULL, -- 'invariant', 'determinism', 'stability', 'time_shift'
    
    -- Verification results
    verification_passed BOOLEAN NOT NULL,
    verification_score DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Test details
    test_name VARCHAR(100) NOT NULL,
    test_description TEXT,
    expected_result JSONB,
    actual_result JSONB,
    deviation_metrics JSONB,
    
    -- Error details (if failed)
    error_message TEXT,
    error_code VARCHAR(20),
    
    -- Performance metrics
    verification_time_ms INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for verification logs
CREATE INDEX idx_signal_verification_logs_type_time 
ON signal_verification_logs(verification_type, timestamp DESC);

CREATE INDEX idx_signal_verification_logs_passed 
ON signal_verification_logs(verification_passed, timestamp DESC);

-- ============================================================================
-- SIGNAL ANOMALY DETECTION
-- ============================================================================

CREATE TABLE signal_anomalies (
    anomaly_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Anomaly details
    anomaly_type VARCHAR(30) NOT NULL, -- 'threshold_breach', 'confidence_drop', 'calculation_error', 'data_quality'
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    
    -- Affected signals
    affected_signals TEXT[], -- Array of signal_ids
    signal_id VARCHAR(50) REFERENCES signal_definitions(signal_id), -- Primary affected signal
    
    -- Anomaly metrics
    anomaly_score DECIMAL(6,4) NOT NULL, -- 0-1 scale
    deviation_magnitude DECIMAL(10,4) DEFAULT 0.0000,
    confidence_impact DECIMAL(6,4) DEFAULT 0.0000,
    
    -- Context
    description TEXT NOT NULL,
    probable_cause TEXT,
    recommended_action TEXT,
    
    -- Resolution tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for anomalies
CREATE INDEX idx_signal_anomalies_severity_time 
ON signal_anomalies(severity, timestamp DESC);

CREATE INDEX idx_signal_anomalies_resolved 
ON signal_anomalies(resolved, timestamp DESC) WHERE NOT resolved;

-- ============================================================================
-- MATERIALIZED VIEWS FOR PERFORMANCE
-- ============================================================================

-- Latest signal values
CREATE MATERIALIZED VIEW latest_signal_values AS
SELECT DISTINCT ON (asset, timeframe, signal_id)
    asset,
    timeframe,
    signal_id,
    timestamp,
    signal_value,
    signal_confidence,
    data_quality_score
FROM signal_calculations
ORDER BY asset, timeframe, signal_id, timestamp DESC;

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX idx_latest_signal_values_unique 
ON latest_signal_values(asset, timeframe, signal_id);

-- Latest onchain scores
CREATE MATERIALIZED VIEW latest_onchain_scores AS
SELECT DISTINCT ON (asset, timeframe)
    asset,
    timeframe,
    timestamp,
    onchain_score,
    confidence,
    bias,
    network_health_score,
    capital_flow_score,
    smart_money_score,
    risk_penalty
FROM onchain_scores
ORDER BY asset, timeframe, timestamp DESC;

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX idx_latest_onchain_scores_unique 
ON latest_onchain_scores(asset, timeframe);

-- Signal performance summary
CREATE MATERIALIZED VIEW signal_performance_summary AS
SELECT 
    s.signal_id,
    s.signal_name,
    s.signal_category,
    COUNT(sc.calculation_id) as total_calculations,
    AVG(sc.signal_confidence) as avg_confidence,
    STDDEV(sc.signal_confidence) as confidence_volatility,
    COUNT(CASE WHEN sc.signal_value = true THEN 1 END)::DECIMAL / COUNT(*) as activation_rate,
    AVG(sc.data_quality_score) as avg_data_quality,
    MAX(sc.timestamp) as last_calculation
FROM signal_definitions s
LEFT JOIN signal_calculations sc ON s.signal_id = sc.signal_id
WHERE s.is_active = true
GROUP BY s.signal_id, s.signal_name, s.signal_category;

-- ============================================================================
-- CONTINUOUS AGGREGATES FOR TIME-SERIES ANALYSIS
-- ============================================================================

-- Hourly signal aggregates
CREATE MATERIALIZED VIEW hourly_signal_summary
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', timestamp) AS hour,
       asset,
       timeframe,
       signal_id,
       COUNT(*) as calculation_count,
       AVG(signal_confidence) as avg_confidence,
       COUNT(CASE WHEN signal_value = true THEN 1 END) as true_count,
       AVG(data_quality_score) as avg_data_quality
FROM signal_calculations
GROUP BY hour, asset, timeframe, signal_id;

-- Daily onchain score aggregates
CREATE MATERIALIZED VIEW daily_score_summary
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', timestamp) AS day,
       asset,
       timeframe,
       COUNT(*) as score_count,
       AVG(onchain_score) as avg_score,
       MIN(onchain_score) as min_score,
       MAX(onchain_score) as max_score,
       AVG(confidence) as avg_confidence,
       COUNT(CASE WHEN bias = 'positive' THEN 1 END) as positive_count,
       COUNT(CASE WHEN bias = 'negative' THEN 1 END) as negative_count,
       COUNT(CASE WHEN bias = 'neutral' THEN 1 END) as neutral_count
FROM onchain_scores
GROUP BY day, asset, timeframe;

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_signal_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY latest_signal_values;
    REFRESH MATERIALIZED VIEW CONCURRENTLY latest_onchain_scores;
    REFRESH MATERIALIZED VIEW signal_performance_summary;
END;
$$ LANGUAGE plpgsql;

-- Function to detect signal anomalies
CREATE OR REPLACE FUNCTION detect_signal_anomalies()
RETURNS TRIGGER AS $$
DECLARE
    avg_confidence DECIMAL(6,4);
    confidence_threshold DECIMAL(6,4) := 0.3;
BEGIN
    -- Check for confidence drops
    SELECT AVG(signal_confidence) INTO avg_confidence
    FROM signal_calculations
    WHERE signal_id = NEW.signal_id
        AND timestamp >= NOW() - INTERVAL '7 days';
    
    IF NEW.signal_confidence < confidence_threshold AND 
       NEW.signal_confidence < (avg_confidence * 0.5) THEN
        
        INSERT INTO signal_anomalies (
            asset, timeframe, timestamp, anomaly_type, severity,
            signal_id, anomaly_score, confidence_impact, description
        ) VALUES (
            NEW.asset, NEW.timeframe, NEW.timestamp, 'confidence_drop', 'medium',
            NEW.signal_id, 1.0 - NEW.signal_confidence, avg_confidence - NEW.signal_confidence,
            'Signal confidence dropped significantly below recent average'
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for anomaly detection
CREATE TRIGGER trigger_detect_signal_anomalies
    AFTER INSERT ON signal_calculations
    FOR EACH ROW
    EXECUTE FUNCTION detect_signal_anomalies();

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Compression policies
SELECT add_compression_policy('signal_calculations', INTERVAL '7 days');
SELECT add_compression_policy('onchain_scores', INTERVAL '7 days');
SELECT add_compression_policy('signal_summary', INTERVAL '7 days');

-- Retention policies (optional - keep 2 years of data)
SELECT add_retention_policy('signal_calculations', INTERVAL '2 years');
SELECT add_retention_policy('onchain_scores', INTERVAL '2 years');
SELECT add_retention_policy('signal_verification_logs', INTERVAL '1 year');

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE signal_definitions IS 'Master table defining all available signals and their calculation parameters';
COMMENT ON TABLE signal_calculations IS 'Time-series storage of individual signal calculation results';
COMMENT ON TABLE onchain_scores IS 'Time-series storage of aggregated OnChain scores and confidence metrics';
COMMENT ON TABLE signal_summary IS 'Aggregated summary statistics for signal analysis';
COMMENT ON TABLE signal_baselines IS 'Historical baseline statistics used for dynamic threshold calculation';
COMMENT ON TABLE signal_stability IS 'Signal stability analysis and reliability tracking';
COMMENT ON TABLE signal_verification_logs IS 'Audit trail for signal verification tests';
COMMENT ON TABLE signal_anomalies IS 'Detected anomalies in signal behavior or calculation';

COMMENT ON COLUMN onchain_scores.onchain_score IS 'Overall OnChain score (0-100 scale)';
COMMENT ON COLUMN onchain_scores.confidence IS 'Overall confidence in the score (0-1 scale)';
COMMENT ON COLUMN onchain_scores.bias IS 'Overall market bias: positive, neutral, or negative';
COMMENT ON COLUMN signal_calculations.signal_confidence IS 'Individual signal confidence (0-1 scale)';
COMMENT ON COLUMN signal_calculations.input_data_hash IS 'SHA-256 hash of input data for reproducibility verification';