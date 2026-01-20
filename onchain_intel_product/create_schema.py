#!/usr/bin/env python3
"""
Simple schema creation script.
"""

import os
import psycopg2

def create_schema():
    """Create database schema."""
    
    # Connect to database
    database_url = os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:Cuongnv123456@localhost:5432/bitcoin_onchain_signals')
    
    print("Connecting to database...")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    print("Connected successfully!")
    
    # Create tables one by one
    tables = [
        # OnChain Scores Table
        """
        CREATE TABLE IF NOT EXISTS onchain_scores (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
            
            onchain_score DECIMAL(5,2) CHECK (onchain_score >= 0 AND onchain_score <= 100),
            confidence DECIMAL(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            bias VARCHAR(10) NOT NULL CHECK (bias IN ('positive', 'neutral', 'negative')),
            
            network_health_score DECIMAL(5,2) CHECK (network_health_score >= 0 AND network_health_score <= 30),
            capital_flow_score DECIMAL(5,2) CHECK (capital_flow_score >= 0 AND capital_flow_score <= 30),
            smart_money_score DECIMAL(5,2) CHECK (smart_money_score >= 0 AND smart_money_score <= 40),
            risk_penalty DECIMAL(5,2) CHECK (risk_penalty >= 0),
            
            signal_count INTEGER NOT NULL DEFAULT 0,
            active_signals INTEGER NOT NULL DEFAULT 0,
            conflicting_signals INTEGER NOT NULL DEFAULT 0,
            
            data_completeness DECIMAL(4,3) NOT NULL CHECK (data_completeness >= 0 AND data_completeness <= 1),
            calculation_time_ms INTEGER NOT NULL DEFAULT 0,
            
            input_data_hash VARCHAR(64),
            calculation_hash VARCHAR(64),
            
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            UNIQUE(timestamp, asset, timeframe)
        )
        """,
        
        # Signal Calculations Table
        """
        CREATE TABLE IF NOT EXISTS signal_calculations (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
            
            signal_id VARCHAR(50) NOT NULL,
            signal_value BOOLEAN NOT NULL,
            signal_strength DECIMAL(4,3) CHECK (signal_strength >= 0 AND signal_strength <= 1),
            
            threshold_used DECIMAL(10,4),
            actual_value DECIMAL(15,6),
            rolling_median DECIMAL(15,6),
            rolling_std DECIMAL(15,6),
            
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            UNIQUE(timestamp, asset, timeframe, signal_id)
        )
        """,
        
        # Signal Verification Logs
        """
        CREATE TABLE IF NOT EXISTS signal_verification_logs (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
            
            test_name VARCHAR(100) NOT NULL,
            verification_passed BOOLEAN NOT NULL,
            verification_score DECIMAL(4,3) CHECK (verification_score >= 0 AND verification_score <= 1),
            
            expected_result JSONB,
            actual_result JSONB,
            error_message TEXT,
            
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        
        # Signal Anomalies
        """
        CREATE TABLE IF NOT EXISTS signal_anomalies (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            
            anomaly_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
            description TEXT NOT NULL,
            
            detected_value DECIMAL(15,6),
            expected_range_min DECIMAL(15,6),
            expected_range_max DECIMAL(15,6),
            confidence DECIMAL(4,3) CHECK (confidence >= 0 AND confidence <= 1),
            
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_at TIMESTAMPTZ,
            resolution_notes TEXT,
            
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        
        # Audit Calculations
        """
        CREATE TABLE IF NOT EXISTS audit_calculations (
            id BIGSERIAL PRIMARY KEY,
            calculation_hash VARCHAR(64) NOT NULL UNIQUE,
            
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
            timestamp TIMESTAMPTZ NOT NULL,
            
            input_data_hash VARCHAR(64) NOT NULL,
            config_hash VARCHAR(64) NOT NULL,
            output_data JSONB NOT NULL,
            
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    ]
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_onchain_scores_asset_timeframe_timestamp ON onchain_scores (asset, timeframe, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_signal_calculations_lookup ON signal_calculations (asset, timeframe, signal_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_verification_logs_lookup ON signal_verification_logs (asset, timeframe, test_name, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_signal_anomalies_unresolved ON signal_anomalies (asset, resolved, timestamp DESC) WHERE NOT resolved",
        "CREATE INDEX IF NOT EXISTS idx_audit_calculations_lookup ON audit_calculations (asset, timeframe, timestamp DESC)"
    ]
    
    print("Creating tables...")
    for i, table_sql in enumerate(tables, 1):
        try:
            cursor.execute(table_sql)
            print(f"Table {i}/5 created")
        except Exception as e:
            print(f"Table {i}/5: {str(e)[:50]}")
    
    print("Creating indexes...")
    for i, index_sql in enumerate(indexes, 1):
        try:
            cursor.execute(index_sql)
            print(f"Index {i}/{len(indexes)} created")
        except Exception as e:
            print(f"Index {i}/{len(indexes)}: {str(e)[:50]}")
    
    # Insert sample data
    print("Inserting sample data...")
    sample_data = """
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
    ) ON CONFLICT (timestamp, asset, timeframe) DO NOTHING
    """
    
    try:
        cursor.execute(sample_data)
        print("Sample data inserted")
    except Exception as e:
        print(f"Sample data: {str(e)[:50]}")
    
    # Commit and close
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Schema creation completed!")

if __name__ == "__main__":
    print("OnChain Intelligence - Schema Creation")
    print("=" * 40)
    
    try:
        create_schema()
        print("\nDatabase setup successful!")
        print("You can now start the API service with: python -m uvicorn main:app --reload")
    except Exception as e:
        print(f"\nError: {e}")
        print("Please check your database connection and try again.")