-- Scheduler State Table
-- Track pipeline scheduler execution

CREATE TABLE IF NOT EXISTS scheduler_state (
    scheduler_name VARCHAR(50) PRIMARY KEY,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'unknown',
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for status queries
CREATE INDEX IF NOT EXISTS idx_scheduler_state_status 
ON scheduler_state(status, last_run DESC);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_scheduler_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_scheduler_state_timestamp ON scheduler_state;
CREATE TRIGGER trigger_scheduler_state_timestamp
    BEFORE UPDATE ON scheduler_state
    FOR EACH ROW
    EXECUTE FUNCTION update_scheduler_state_timestamp();

-- Insert default state
INSERT INTO scheduler_state (scheduler_name, status)
VALUES ('onchain_pipeline', 'initialized')
ON CONFLICT (scheduler_name) DO NOTHING;
