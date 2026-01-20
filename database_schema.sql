-- Bitcoin Raw Data Collector - PostgreSQL Schema
-- Optimized for UTXO-based blockchain data storage and analysis

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- SYNC STATE MANAGEMENT
-- ============================================================================

CREATE TABLE sync_state (
    id SERIAL PRIMARY KEY,
    chain VARCHAR(10) NOT NULL DEFAULT 'BTC',
    last_synced_block_height BIGINT NOT NULL DEFAULT 0,
    last_synced_block_hash VARCHAR(64),
    sync_started_at TIMESTAMP WITH TIME ZONE,
    sync_completed_at TIMESTAMP WITH TIME ZONE,
    is_syncing BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure single row for BTC chain
CREATE UNIQUE INDEX idx_sync_state_chain ON sync_state(chain);

-- ============================================================================
-- BLOCK-LEVEL DATA
-- ============================================================================

CREATE TABLE blocks (
    block_height BIGINT PRIMARY KEY,
    block_hash VARCHAR(64) NOT NULL UNIQUE,
    block_time TIMESTAMP WITH TIME ZONE NOT NULL,
    tx_count INTEGER NOT NULL DEFAULT 0,
    total_fees_btc DECIMAL(16,8) DEFAULT 0,
    block_size_bytes INTEGER,
    difficulty DECIMAL(20,8),
    nonce BIGINT,
    merkle_root VARCHAR(64),
    previous_block_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for block queries
CREATE INDEX idx_blocks_hash ON blocks(block_hash);
CREATE INDEX idx_blocks_time ON blocks(block_time);
CREATE INDEX idx_blocks_height_desc ON blocks(block_height DESC);

-- ============================================================================
-- TRANSACTION-LEVEL DATA
-- ============================================================================

CREATE TABLE transactions (
    tx_hash VARCHAR(64) PRIMARY KEY,
    block_height BIGINT NOT NULL REFERENCES blocks(block_height) ON DELETE CASCADE,
    block_time TIMESTAMP WITH TIME ZONE NOT NULL,
    tx_index INTEGER NOT NULL, -- Position within block
    input_count INTEGER NOT NULL DEFAULT 0,
    output_count INTEGER NOT NULL DEFAULT 0,
    total_input_btc DECIMAL(16,8) DEFAULT 0,
    total_output_btc DECIMAL(16,8) DEFAULT 0,
    fee_btc DECIMAL(16,8) DEFAULT 0,
    is_coinbase BOOLEAN DEFAULT FALSE,
    tx_size_bytes INTEGER,
    tx_weight INTEGER,
    locktime BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for transaction queries
CREATE INDEX idx_transactions_block_height ON transactions(block_height);
CREATE INDEX idx_transactions_block_time ON transactions(block_time);
CREATE INDEX idx_transactions_fee_desc ON transactions(fee_btc DESC);
CREATE INDEX idx_transactions_is_coinbase ON transactions(is_coinbase);
CREATE UNIQUE INDEX idx_transactions_block_position ON transactions(block_height, tx_index);

-- ============================================================================
-- UTXO-LEVEL DATA (OUTPUTS)
-- ============================================================================

CREATE TABLE utxos (
    utxo_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tx_hash VARCHAR(64) NOT NULL REFERENCES transactions(tx_hash) ON DELETE CASCADE,
    vout_index INTEGER NOT NULL,
    address VARCHAR(62), -- P2PKH/P2SH/Bech32 addresses (NULL for non-standard)
    script_type VARCHAR(20), -- P2PKH, P2SH, P2WPKH, P2WSH, P2TR, etc.
    script_hex TEXT,
    value_btc DECIMAL(16,8) NOT NULL,
    is_spent BOOLEAN DEFAULT FALSE,
    spent_tx_hash VARCHAR(64), -- References transactions(tx_hash)
    spent_block_height BIGINT, -- References blocks(block_height)
    spent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint on UTXO identifier
CREATE UNIQUE INDEX idx_utxos_outpoint ON utxos(tx_hash, vout_index);

-- Indexes for UTXO queries
CREATE INDEX idx_utxos_address ON utxos(address) WHERE address IS NOT NULL;
CREATE INDEX idx_utxos_is_spent ON utxos(is_spent);
CREATE INDEX idx_utxos_spent_tx ON utxos(spent_tx_hash) WHERE spent_tx_hash IS NOT NULL;
CREATE INDEX idx_utxos_value_desc ON utxos(value_btc DESC);
CREATE INDEX idx_utxos_script_type ON utxos(script_type);

-- Partial index for unspent UTXOs (most common query)
CREATE INDEX idx_utxos_unspent_address ON utxos(address, value_btc DESC) 
WHERE is_spent = FALSE AND address IS NOT NULL;

-- ============================================================================
-- TRANSACTION INPUTS (SPENDING REFERENCES)
-- ============================================================================

CREATE TABLE transaction_inputs (
    input_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tx_hash VARCHAR(64) NOT NULL REFERENCES transactions(tx_hash) ON DELETE CASCADE,
    input_index INTEGER NOT NULL,
    previous_tx_hash VARCHAR(64), -- NULL for coinbase
    previous_vout_index INTEGER, -- NULL for coinbase
    script_sig_hex TEXT,
    witness_data JSONB, -- For SegWit transactions
    sequence_number BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint on input position
CREATE UNIQUE INDEX idx_inputs_position ON transaction_inputs(tx_hash, input_index);

-- Indexes for input queries
CREATE INDEX idx_inputs_previous_outpoint ON transaction_inputs(previous_tx_hash, previous_vout_index)
WHERE previous_tx_hash IS NOT NULL;

-- ============================================================================
-- ADDRESS-LEVEL AGGREGATED DATA
-- ============================================================================

CREATE TABLE addresses (
    address VARCHAR(62) PRIMARY KEY,
    script_type VARCHAR(20),
    first_seen_block BIGINT NOT NULL,
    last_seen_block BIGINT NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    total_received_btc DECIMAL(16,8) DEFAULT 0,
    total_sent_btc DECIMAL(16,8) DEFAULT 0,
    current_balance_btc DECIMAL(16,8) DEFAULT 0,
    tx_count INTEGER DEFAULT 0,
    utxo_count INTEGER DEFAULT 0, -- Current unspent outputs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for address queries
CREATE INDEX idx_addresses_balance_desc ON addresses(current_balance_btc DESC);
CREATE INDEX idx_addresses_tx_count_desc ON addresses(tx_count DESC);
CREATE INDEX idx_addresses_first_seen ON addresses(first_seen_block);
CREATE INDEX idx_addresses_last_seen ON addresses(last_seen_block);
CREATE INDEX idx_addresses_script_type ON addresses(script_type);

-- ============================================================================
-- PERFORMANCE OPTIMIZATION TABLES
-- ============================================================================

-- Daily aggregated statistics for faster queries
CREATE TABLE daily_stats (
    stat_date DATE PRIMARY KEY,
    block_count INTEGER DEFAULT 0,
    tx_count INTEGER DEFAULT 0,
    total_volume_btc DECIMAL(20,8) DEFAULT 0,
    total_fees_btc DECIMAL(16,8) DEFAULT 0,
    avg_tx_size_bytes DECIMAL(10,2),
    avg_fee_per_byte DECIMAL(10,8),
    active_addresses INTEGER DEFAULT 0,
    new_addresses INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- TRIGGERS FOR DATA CONSISTENCY
-- ============================================================================

-- Update sync_state timestamp on changes
CREATE OR REPLACE FUNCTION update_sync_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sync_state_updated_at
    BEFORE UPDATE ON sync_state
    FOR EACH ROW
    EXECUTE FUNCTION update_sync_state_timestamp();

-- Update address timestamp on changes
CREATE OR REPLACE FUNCTION update_address_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_address_updated_at
    BEFORE UPDATE ON addresses
    FOR EACH ROW
    EXECUTE FUNCTION update_address_timestamp();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Initialize sync state for Bitcoin
INSERT INTO sync_state (chain, last_synced_block_height) 
VALUES ('BTC', 0) 
ON CONFLICT (chain) DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Recent blocks with transaction summary
CREATE VIEW recent_blocks AS
SELECT 
    b.block_height,
    b.block_hash,
    b.block_time,
    b.tx_count,
    b.total_fees_btc,
    COALESCE(SUM(t.total_output_btc), 0) as total_volume_btc
FROM blocks b
LEFT JOIN transactions t ON b.block_height = t.block_height
WHERE b.block_time >= NOW() - INTERVAL '7 days'
GROUP BY b.block_height, b.block_hash, b.block_time, b.tx_count, b.total_fees_btc
ORDER BY b.block_height DESC;

-- Top addresses by balance
CREATE VIEW top_addresses AS
SELECT 
    address,
    current_balance_btc,
    tx_count,
    total_received_btc,
    total_sent_btc,
    first_seen_at,
    last_seen_at
FROM addresses
WHERE current_balance_btc > 0
ORDER BY current_balance_btc DESC;

-- Unspent transaction outputs (UTXO set)
CREATE VIEW utxo_set AS
SELECT 
    u.tx_hash,
    u.vout_index,
    u.address,
    u.value_btc,
    u.script_type,
    t.block_height,
    t.block_time
FROM utxos u
JOIN transactions t ON u.tx_hash = t.tx_hash
WHERE u.is_spent = FALSE
ORDER BY u.value_btc DESC;

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE blocks IS 'Block-level data from Bitcoin blockchain';
COMMENT ON TABLE transactions IS 'Transaction-level data with fee calculations';
COMMENT ON TABLE utxos IS 'UTXO tracking with spending status';
COMMENT ON TABLE transaction_inputs IS 'Transaction inputs with previous output references';
COMMENT ON TABLE addresses IS 'Address-level aggregated statistics';
COMMENT ON TABLE sync_state IS 'Synchronization state management';
COMMENT ON TABLE daily_stats IS 'Daily aggregated statistics for performance';

COMMENT ON COLUMN utxos.utxo_id IS 'Unique identifier for each UTXO';
COMMENT ON COLUMN utxos.script_type IS 'Output script type (P2PKH, P2SH, P2WPKH, etc.)';
COMMENT ON COLUMN addresses.current_balance_btc IS 'Current balance (received - sent)';
COMMENT ON COLUMN transactions.fee_btc IS 'Transaction fee (input_total - output_total)';