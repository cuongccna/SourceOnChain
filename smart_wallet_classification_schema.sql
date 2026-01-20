-- Smart Wallet Classification Engine - Database Schema
-- Behavioral classification of Bitcoin addresses using on-chain data

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- WALLET BEHAVIOR FEATURES
-- ============================================================================

CREATE TABLE wallet_behavior_features (
    address VARCHAR(62) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '30d', '90d', '1y'
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Data quality metrics
    transaction_count INTEGER NOT NULL,
    active_days INTEGER NOT NULL,
    first_tx_date TIMESTAMP WITH TIME ZONE NOT NULL,
    last_tx_date TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 1. Holding Behavior Features
    avg_utxo_holding_time_days DECIMAL(10,2) NOT NULL DEFAULT 0,
    holding_time_p25_days DECIMAL(10,2) DEFAULT 0,
    holding_time_p50_days DECIMAL(10,2) DEFAULT 0,
    holding_time_p75_days DECIMAL(10,2) DEFAULT 0,
    holding_time_p90_days DECIMAL(10,2) DEFAULT 0,
    dormancy_activation_rate DECIMAL(6,4) DEFAULT 0, -- 0-1 scale
    
    -- 2. Capital Efficiency Features (PnL Proxy)
    realized_profit_btc DECIMAL(16,8) DEFAULT 0,
    realized_loss_btc DECIMAL(16,8) DEFAULT 0,
    net_realized_pnl_btc DECIMAL(16,8) DEFAULT 0,
    profit_loss_ratio DECIMAL(10,4) DEFAULT 0,
    win_rate DECIMAL(6,4) NOT NULL DEFAULT 0, -- 0-1 scale
    profitable_spends INTEGER DEFAULT 0,
    total_spends INTEGER DEFAULT 0,
    
    -- 3. Timing Quality Features
    accumulation_before_whale_spike_rate DECIMAL(6,4) DEFAULT 0,
    distribution_after_whale_spike_rate DECIMAL(6,4) DEFAULT 0,
    accumulation_periods_count INTEGER DEFAULT 0,
    distribution_periods_count INTEGER DEFAULT 0,
    successful_accumulations INTEGER DEFAULT 0,
    successful_distributions INTEGER DEFAULT 0,
    
    -- 4. Activity Discipline Features
    tx_frequency_per_day DECIMAL(8,4) DEFAULT 0,
    tx_frequency_std DECIMAL(8,4) DEFAULT 0,
    burst_vs_consistency_score DECIMAL(6,4) DEFAULT 0, -- 0-1 scale (1=consistent)
    overtrading_penalty DECIMAL(6,4) DEFAULT 0, -- 0-1 scale (0=no penalty)
    avg_tx_interval_hours DECIMAL(10,2) DEFAULT 0,
    
    -- Network-relative percentiles (0-1 scale)
    avg_holding_time_percentile DECIMAL(6,4) DEFAULT 0,
    win_rate_percentile DECIMAL(6,4) DEFAULT 0,
    profit_loss_ratio_percentile DECIMAL(6,4) DEFAULT 0,
    net_pnl_percentile DECIMAL(6,4) DEFAULT 0,
    tx_frequency_std_percentile DECIMAL(6,4) DEFAULT 0,
    
    -- Additional behavioral metrics
    round_number_tx_ratio DECIMAL(6,4) DEFAULT 0, -- Exchange indicator
    coinbase_tx_ratio DECIMAL(6,4) DEFAULT 0, -- Mining indicator
    avg_inputs_per_tx DECIMAL(8,2) DEFAULT 0,
    avg_outputs_per_tx DECIMAL(8,2) DEFAULT 0,
    avg_tx_value_btc DECIMAL(16,8) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (address, timeframe, calculation_timestamp)
);

-- Indexes for wallet behavior features
CREATE INDEX idx_wallet_behavior_features_address 
ON wallet_behavior_features(address);

CREATE INDEX idx_wallet_behavior_features_timeframe_calc_time 
ON wallet_behavior_features(timeframe, calculation_timestamp DESC);

CREATE INDEX idx_wallet_behavior_features_win_rate 
ON wallet_behavior_features(win_rate DESC, timeframe);

CREATE INDEX idx_wallet_behavior_features_pnl 
ON wallet_behavior_features(net_realized_pnl_btc DESC, timeframe);

CREATE INDEX idx_wallet_behavior_features_holding_time 
ON wallet_behavior_features(avg_utxo_holding_time_days DESC, timeframe);

-- ============================================================================
-- WALLET CLASSIFICATION RESULTS
-- ============================================================================

CREATE TABLE wallet_classification (
    address VARCHAR(62) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Classification results
    class_label VARCHAR(20) NOT NULL, -- 'SMART_MONEY', 'NEUTRAL_CAPITAL', 'DUMB_MONEY', 'NOISE'
    confidence_score DECIMAL(6,4) NOT NULL, -- 0-1 scale
    
    -- Composite scores (0-1 scale)
    holding_behavior_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    pnl_efficiency_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    timing_quality_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    activity_discipline_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    overall_smart_money_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    
    -- Feature contributions to classification
    holding_contribution DECIMAL(6,4) DEFAULT 0,
    pnl_contribution DECIMAL(6,4) DEFAULT 0,
    timing_contribution DECIMAL(6,4) DEFAULT 0,
    discipline_contribution DECIMAL(6,4) DEFAULT 0,
    
    -- Classification metadata
    meets_smart_money_requirements BOOLEAN DEFAULT FALSE,
    meets_dumb_money_criteria BOOLEAN DEFAULT FALSE,
    excluded_as_noise BOOLEAN DEFAULT FALSE,
    exclusion_reason VARCHAR(50), -- 'insufficient_data', 'exchange_pattern', etc.
    
    -- Statistical validation
    classification_significant BOOLEAN DEFAULT FALSE,
    effect_size_vs_network DECIMAL(6,4) DEFAULT 0,
    sample_size_adequate BOOLEAN DEFAULT FALSE,
    
    -- Multi-timeframe consistency (when available)
    consistency_score DECIMAL(6,4), -- Consistency across timeframes
    majority_vote_classification VARCHAR(20), -- Final classification across timeframes
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (address, timeframe, calculation_timestamp)
);

-- Indexes for wallet classification
CREATE INDEX idx_wallet_classification_class_label 
ON wallet_classification(class_label, timeframe);

CREATE INDEX idx_wallet_classification_confidence 
ON wallet_classification(confidence_score DESC, class_label);

CREATE INDEX idx_wallet_classification_smart_money_score 
ON wallet_classification(overall_smart_money_score DESC, timeframe);

CREATE INDEX idx_wallet_classification_timestamp 
ON wallet_classification(calculation_timestamp DESC);

-- Partial indexes for specific classifications
CREATE INDEX idx_wallet_classification_smart_money 
ON wallet_classification(address, confidence_score DESC) 
WHERE class_label = 'SMART_MONEY';

CREATE INDEX idx_wallet_classification_dumb_money 
ON wallet_classification(address, confidence_score DESC) 
WHERE class_label = 'DUMB_MONEY';

-- ============================================================================
-- NETWORK STATISTICS CACHE
-- ============================================================================

CREATE TABLE network_behavior_stats (
    calculation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    
    -- Sample size
    total_addresses_analyzed INTEGER NOT NULL,
    addresses_excluded_as_noise INTEGER DEFAULT 0,
    
    -- Holding behavior network stats
    network_median_holding_time_days DECIMAL(10,2) NOT NULL,
    network_p25_holding_time_days DECIMAL(10,2) DEFAULT 0,
    network_p75_holding_time_days DECIMAL(10,2) DEFAULT 0,
    
    -- PnL efficiency network stats
    network_median_win_rate DECIMAL(6,4) NOT NULL,
    network_p25_win_rate DECIMAL(6,4) DEFAULT 0,
    network_p75_win_rate DECIMAL(6,4) DEFAULT 0,
    network_median_pnl_ratio DECIMAL(10,4) DEFAULT 0,
    
    -- Activity discipline network stats
    network_median_tx_frequency DECIMAL(8,4) NOT NULL,
    network_median_consistency_score DECIMAL(6,4) DEFAULT 0,
    
    -- Classification distribution
    smart_money_percentage DECIMAL(6,4) DEFAULT 0,
    neutral_capital_percentage DECIMAL(6,4) DEFAULT 0,
    dumb_money_percentage DECIMAL(6,4) DEFAULT 0,
    noise_percentage DECIMAL(6,4) DEFAULT 0,
    
    -- Quality metrics
    avg_confidence_score DECIMAL(6,4) DEFAULT 0,
    classification_consistency_score DECIMAL(6,4) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (calculation_timestamp, timeframe)
);

-- Index for network stats
CREATE INDEX idx_network_behavior_stats_timeframe_time 
ON network_behavior_stats(timeframe, calculation_timestamp DESC);

-- ============================================================================
-- CLASSIFICATION HISTORY TRACKING
-- ============================================================================

CREATE TABLE wallet_classification_history (
    address VARCHAR(62) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    classification_date DATE NOT NULL,
    
    -- Historical classification
    class_label VARCHAR(20) NOT NULL,
    confidence_score DECIMAL(6,4) NOT NULL,
    overall_smart_money_score DECIMAL(6,4) NOT NULL,
    
    -- Change tracking
    previous_class_label VARCHAR(20),
    class_changed BOOLEAN DEFAULT FALSE,
    confidence_change DECIMAL(6,4) DEFAULT 0,
    score_change DECIMAL(6,4) DEFAULT 0,
    
    -- Stability metrics
    days_in_current_class INTEGER DEFAULT 1,
    total_class_changes INTEGER DEFAULT 0,
    classification_stability_score DECIMAL(6,4) DEFAULT 1, -- 1 = most stable
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (address, timeframe, classification_date)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('wallet_classification_history', 'classification_date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Indexes for classification history
CREATE INDEX idx_wallet_classification_history_address 
ON wallet_classification_history(address, classification_date DESC);

CREATE INDEX idx_wallet_classification_history_class_changes 
ON wallet_classification_history(class_changed, classification_date DESC) 
WHERE class_changed = TRUE;

-- ============================================================================
-- SMART MONEY COHORT ANALYSIS
-- ============================================================================

CREATE TABLE smart_money_cohorts (
    cohort_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_name VARCHAR(100) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    creation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Cohort definition criteria
    min_confidence_score DECIMAL(6,4) NOT NULL,
    min_smart_money_score DECIMAL(6,4) NOT NULL,
    min_transaction_count INTEGER DEFAULT 20,
    min_active_days INTEGER DEFAULT 30,
    
    -- Cohort statistics
    total_addresses INTEGER NOT NULL,
    avg_confidence_score DECIMAL(6,4) DEFAULT 0,
    avg_smart_money_score DECIMAL(6,4) DEFAULT 0,
    avg_win_rate DECIMAL(6,4) DEFAULT 0,
    avg_holding_time_days DECIMAL(10,2) DEFAULT 0,
    
    -- Performance tracking
    cohort_performance_score DECIMAL(6,4) DEFAULT 0,
    cohort_consistency_score DECIMAL(6,4) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cohort membership table
CREATE TABLE smart_money_cohort_members (
    cohort_id UUID NOT NULL REFERENCES smart_money_cohorts(cohort_id),
    address VARCHAR(62) NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Member metrics at time of joining
    confidence_score DECIMAL(6,4) NOT NULL,
    smart_money_score DECIMAL(6,4) NOT NULL,
    classification_timeframe VARCHAR(10) NOT NULL,
    
    PRIMARY KEY (cohort_id, address)
);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest wallet classifications
CREATE VIEW latest_wallet_classifications AS
SELECT DISTINCT ON (address, timeframe)
    address,
    timeframe,
    class_label,
    confidence_score,
    overall_smart_money_score,
    holding_behavior_score,
    pnl_efficiency_score,
    timing_quality_score,
    activity_discipline_score,
    calculation_timestamp
FROM wallet_classification
ORDER BY address, timeframe, calculation_timestamp DESC;

-- Smart money wallets summary
CREATE VIEW smart_money_wallets AS
SELECT 
    address,
    timeframe,
    confidence_score,
    overall_smart_money_score,
    calculation_timestamp
FROM latest_wallet_classifications
WHERE class_label = 'SMART_MONEY'
ORDER BY overall_smart_money_score DESC;

-- Classification distribution summary
CREATE VIEW classification_distribution AS
SELECT 
    timeframe,
    class_label,
    COUNT(*) as wallet_count,
    AVG(confidence_score) as avg_confidence,
    AVG(overall_smart_money_score) as avg_score
FROM latest_wallet_classifications
WHERE class_label != 'NOISE'
GROUP BY timeframe, class_label
ORDER BY timeframe, 
    CASE class_label 
        WHEN 'SMART_MONEY' THEN 1 
        WHEN 'NEUTRAL_CAPITAL' THEN 2 
        WHEN 'DUMB_MONEY' THEN 3 
    END;

-- High confidence classifications
CREATE VIEW high_confidence_classifications AS
SELECT 
    address,
    timeframe,
    class_label,
    confidence_score,
    overall_smart_money_score
FROM latest_wallet_classifications
WHERE confidence_score >= 0.8
    AND class_label IN ('SMART_MONEY', 'DUMB_MONEY')
ORDER BY confidence_score DESC;

-- ============================================================================
-- TRIGGERS AND FUNCTIONS
-- ============================================================================

-- Function to update classification history
CREATE OR REPLACE FUNCTION update_classification_history()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert into history table
    INSERT INTO wallet_classification_history (
        address, timeframe, classification_date,
        class_label, confidence_score, overall_smart_money_score,
        previous_class_label, class_changed, confidence_change, score_change
    )
    SELECT 
        NEW.address,
        NEW.timeframe,
        NEW.calculation_timestamp::date,
        NEW.class_label,
        NEW.confidence_score,
        NEW.overall_smart_money_score,
        OLD.class_label,
        (NEW.class_label != COALESCE(OLD.class_label, '')),
        NEW.confidence_score - COALESCE(OLD.confidence_score, 0),
        NEW.overall_smart_money_score - COALESCE(OLD.overall_smart_money_score, 0)
    ON CONFLICT (address, timeframe, classification_date) 
    DO UPDATE SET
        class_label = EXCLUDED.class_label,
        confidence_score = EXCLUDED.confidence_score,
        overall_smart_money_score = EXCLUDED.overall_smart_money_score,
        class_changed = EXCLUDED.class_changed,
        confidence_change = EXCLUDED.confidence_change,
        score_change = EXCLUDED.score_change;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for classification history
CREATE TRIGGER trigger_update_classification_history
    AFTER INSERT OR UPDATE ON wallet_classification
    FOR EACH ROW
    EXECUTE FUNCTION update_classification_history();

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Compression for historical data
ALTER TABLE wallet_behavior_features SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'address,timeframe'
);

ALTER TABLE wallet_classification SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'address,timeframe'
);

-- Continuous aggregates for classification metrics
CREATE MATERIALIZED VIEW daily_classification_summary
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', calculation_timestamp) AS day,
       timeframe,
       class_label,
       COUNT(*) as classification_count,
       AVG(confidence_score) as avg_confidence,
       AVG(overall_smart_money_score) as avg_score
FROM wallet_classification
GROUP BY day, timeframe, class_label;

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE wallet_behavior_features IS 'Behavioral features extracted from on-chain wallet activity';
COMMENT ON TABLE wallet_classification IS 'Smart wallet classification results with confidence scores';
COMMENT ON TABLE network_behavior_stats IS 'Network-wide behavioral statistics for normalization';
COMMENT ON TABLE wallet_classification_history IS 'Historical tracking of wallet classification changes';

COMMENT ON COLUMN wallet_behavior_features.win_rate IS 'Ratio of profitable spends to total spends (0-1)';
COMMENT ON COLUMN wallet_behavior_features.profit_loss_ratio IS 'Ratio of realized profits to realized losses';
COMMENT ON COLUMN wallet_classification.class_label IS 'SMART_MONEY, NEUTRAL_CAPITAL, DUMB_MONEY, or NOISE';
COMMENT ON COLUMN wallet_classification.confidence_score IS 'Classification confidence (0-1 scale)';
COMMENT ON COLUMN wallet_classification.overall_smart_money_score IS 'Composite smart money score (0-1 scale)';