"""
Database Persistence Layer for OnChain Data.

Stores collected metrics, whale data, and signals to PostgreSQL.
Supports both raw storage and time-series queries.
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import hashlib
import json

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool
import structlog

logger = structlog.get_logger(__name__)


class DatabaseConfig:
    """Database configuration from environment."""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', 5432))
        self.name = os.getenv('DB_NAME', 'bitcoin_onchain_signals')
        self.user = os.getenv('DB_USER', 'onchain_user')
        self.password = os.getenv('DB_PASSWORD', '')
        
        # Connection pool settings
        self.min_connections = int(os.getenv('DB_POOL_MIN', 2))
        self.max_connections = int(os.getenv('DB_POOL_MAX', 10))
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def dsn(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'dbname': self.name,
            'user': self.user,
            'password': self.password
        }


class OnChainDatabase:
    """
    Database persistence layer for OnChain data.
    
    Features:
    - Connection pooling
    - Transaction management
    - Upsert support
    - Time-series queries
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool = None
        self._initialized = False
        
        logger.info("OnChainDatabase initialized", 
                   host=self.config.host, 
                   database=self.config.name)
    
    def connect(self):
        """Initialize connection pool."""
        if self._pool is not None:
            return
        
        try:
            self._pool = ThreadedConnectionPool(
                self.config.min_connections,
                self.config.max_connections,
                **self.config.dsn
            )
            logger.info("Database connection pool created",
                       min_conn=self.config.min_connections,
                       max_conn=self.config.max_connections)
        except Exception as e:
            logger.error("Failed to create connection pool", error=str(e))
            raise
    
    def close(self):
        """Close all connections."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Database connection pool closed")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        if self._pool is None:
            self.connect()
        
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Get a cursor with automatic cleanup."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def ensure_tables(self):
        """Ensure required tables exist (simplified version)."""
        
        create_tables_sql = """
        -- OnChain Metrics Table (simplified)
        CREATE TABLE IF NOT EXISTS onchain_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
            
            -- Blockchain metrics
            block_height BIGINT,
            blocks_analyzed INTEGER,
            total_transactions INTEGER,
            avg_block_size DECIMAL(20,2),
            avg_txs_per_block DECIMAL(10,2),
            
            -- Mempool metrics
            pending_txs INTEGER,
            mempool_size_mb DECIMAL(10,4),
            total_fees_btc DECIMAL(16,8),
            fastest_fee INTEGER,
            hour_fee INTEGER,
            
            -- Whale metrics
            whale_tx_count INTEGER,
            whale_volume_btc DECIMAL(20,8),
            whale_inflow_btc DECIMAL(20,8),
            whale_outflow_btc DECIMAL(20,8),
            net_whale_flow_btc DECIMAL(20,8),
            whale_dominance DECIMAL(8,6),
            
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            UNIQUE(timestamp, asset, timeframe)
        );
        
        CREATE INDEX IF NOT EXISTS idx_onchain_metrics_time 
        ON onchain_metrics(timestamp DESC);
        
        CREATE INDEX IF NOT EXISTS idx_onchain_metrics_asset_timeframe 
        ON onchain_metrics(asset, timeframe, timestamp DESC);
        
        -- OnChain Signals Table
        CREATE TABLE IF NOT EXISTS onchain_signals (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            asset VARCHAR(10) NOT NULL DEFAULT 'BTC',
            timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
            
            -- Signals
            smart_money_accumulation BOOLEAN,
            whale_flow_dominant BOOLEAN,
            network_growth BOOLEAN,
            distribution_risk BOOLEAN,
            
            -- Score
            onchain_score DECIMAL(6,2),
            bias VARCHAR(10),
            confidence DECIMAL(6,4),
            
            -- State
            state VARCHAR(20),
            
            -- Verification
            data_hash VARCHAR(64),
            
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            UNIQUE(timestamp, asset, timeframe)
        );
        
        CREATE INDEX IF NOT EXISTS idx_onchain_signals_time 
        ON onchain_signals(timestamp DESC);
        
        CREATE INDEX IF NOT EXISTS idx_onchain_signals_bias 
        ON onchain_signals(bias, timestamp DESC);
        
        -- Whale Transactions Log
        CREATE TABLE IF NOT EXISTS whale_transactions (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            txid VARCHAR(64) NOT NULL,
            block_height BIGINT,
            value_btc DECIMAL(20,8) NOT NULL,
            tier VARCHAR(20) NOT NULL,  -- large, whale, ultra_whale, leviathan
            flow_type VARCHAR(20),  -- inflow, outflow, internal, unknown
            fee_btc DECIMAL(16,8),
            input_count INTEGER,
            output_count INTEGER,
            
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            UNIQUE(txid)
        );
        
        CREATE INDEX IF NOT EXISTS idx_whale_transactions_time 
        ON whale_transactions(timestamp DESC);
        
        CREATE INDEX IF NOT EXISTS idx_whale_transactions_tier 
        ON whale_transactions(tier, timestamp DESC);
        
        CREATE INDEX IF NOT EXISTS idx_whale_transactions_value 
        ON whale_transactions(value_btc DESC);
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(create_tables_sql)
        
        self._initialized = True
        logger.info("Database tables ensured")
    
    # ========================================================
    # METRICS PERSISTENCE
    # ========================================================
    
    def save_metrics(self, metrics: Dict[str, Any], 
                    asset: str = 'BTC', 
                    timeframe: str = '1h') -> bool:
        """
        Save collected metrics to database.
        
        Args:
            metrics: Dictionary with blockchain, mempool, whale data
            asset: Asset symbol
            timeframe: Timeframe
            
        Returns:
            True if saved successfully
        """
        if not self._initialized:
            self.ensure_tables()
        
        timestamp = datetime.utcnow()
        blockchain = metrics.get('blockchain', {})
        mempool = metrics.get('mempool', {})
        whale = metrics.get('whale', {})
        
        sql = """
        INSERT INTO onchain_metrics (
            timestamp, asset, timeframe,
            block_height, blocks_analyzed, total_transactions,
            avg_block_size, avg_txs_per_block,
            pending_txs, mempool_size_mb, total_fees_btc,
            fastest_fee, hour_fee,
            whale_tx_count, whale_volume_btc, whale_inflow_btc,
            whale_outflow_btc, net_whale_flow_btc, whale_dominance
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (timestamp, asset, timeframe) 
        DO UPDATE SET
            block_height = EXCLUDED.block_height,
            blocks_analyzed = EXCLUDED.blocks_analyzed,
            total_transactions = EXCLUDED.total_transactions,
            avg_block_size = EXCLUDED.avg_block_size,
            avg_txs_per_block = EXCLUDED.avg_txs_per_block,
            pending_txs = EXCLUDED.pending_txs,
            mempool_size_mb = EXCLUDED.mempool_size_mb,
            total_fees_btc = EXCLUDED.total_fees_btc,
            fastest_fee = EXCLUDED.fastest_fee,
            hour_fee = EXCLUDED.hour_fee,
            whale_tx_count = EXCLUDED.whale_tx_count,
            whale_volume_btc = EXCLUDED.whale_volume_btc,
            whale_inflow_btc = EXCLUDED.whale_inflow_btc,
            whale_outflow_btc = EXCLUDED.whale_outflow_btc,
            net_whale_flow_btc = EXCLUDED.net_whale_flow_btc,
            whale_dominance = EXCLUDED.whale_dominance
        """
        
        values = (
            timestamp, asset, timeframe,
            blockchain.get('block_height'),
            blockchain.get('blocks_analyzed'),
            blockchain.get('total_transactions'),
            blockchain.get('avg_block_size'),
            blockchain.get('avg_txs_per_block'),
            mempool.get('pending_txs'),
            mempool.get('mempool_size_mb'),
            mempool.get('total_fees_btc'),
            mempool.get('fastest_fee'),
            mempool.get('hour_fee'),
            whale.get('whale_tx_count'),
            whale.get('whale_volume_btc'),
            whale.get('whale_inflow'),
            whale.get('whale_outflow'),
            whale.get('net_whale_flow'),
            whale.get('whale_dominance')
        )
        
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, values)
            logger.debug("Metrics saved", timestamp=timestamp, asset=asset)
            return True
        except Exception as e:
            logger.error("Failed to save metrics", error=str(e))
            return False
    
    # ========================================================
    # SIGNALS PERSISTENCE
    # ========================================================
    
    def save_signals(self, signals: Dict[str, bool], 
                    score: float, bias: str, confidence: float,
                    state: str,
                    asset: str = 'BTC', 
                    timeframe: str = '1h',
                    data_hash: Optional[str] = None) -> bool:
        """
        Save signal calculations to database.
        
        Args:
            signals: Dictionary of signal values
            score: OnChain score
            bias: Bias (positive/neutral/negative)
            confidence: Confidence level
            state: System state (ACTIVE/DEGRADED/BLOCKED)
            asset: Asset symbol
            timeframe: Timeframe
            data_hash: Optional hash of input data
            
        Returns:
            True if saved successfully
        """
        if not self._initialized:
            self.ensure_tables()
        
        timestamp = datetime.utcnow()
        
        # Generate data hash if not provided
        if data_hash is None:
            data_str = json.dumps(signals, sort_keys=True)
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:64]
        
        sql = """
        INSERT INTO onchain_signals (
            timestamp, asset, timeframe,
            smart_money_accumulation, whale_flow_dominant,
            network_growth, distribution_risk,
            onchain_score, bias, confidence, state, data_hash
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (timestamp, asset, timeframe) 
        DO UPDATE SET
            smart_money_accumulation = EXCLUDED.smart_money_accumulation,
            whale_flow_dominant = EXCLUDED.whale_flow_dominant,
            network_growth = EXCLUDED.network_growth,
            distribution_risk = EXCLUDED.distribution_risk,
            onchain_score = EXCLUDED.onchain_score,
            bias = EXCLUDED.bias,
            confidence = EXCLUDED.confidence,
            state = EXCLUDED.state,
            data_hash = EXCLUDED.data_hash
        """
        
        values = (
            timestamp, asset, timeframe,
            signals.get('smart_money_accumulation'),
            signals.get('whale_flow_dominant'),
            signals.get('network_growth'),
            signals.get('distribution_risk'),
            score, bias, confidence, state, data_hash
        )
        
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, values)
            logger.debug("Signals saved", timestamp=timestamp, score=score, bias=bias)
            return True
        except Exception as e:
            logger.error("Failed to save signals", error=str(e))
            return False
    
    # ========================================================
    # WHALE TRANSACTIONS PERSISTENCE
    # ========================================================
    
    def save_whale_transactions(self, transactions: List[Dict[str, Any]]) -> int:
        """
        Save whale transactions to database.
        
        Args:
            transactions: List of whale transaction dicts
            
        Returns:
            Number of transactions saved
        """
        if not self._initialized:
            self.ensure_tables()
        
        if not transactions:
            return 0
        
        sql = """
        INSERT INTO whale_transactions (
            timestamp, txid, block_height, value_btc, tier,
            flow_type, fee_btc, input_count, output_count
        ) VALUES %s
        ON CONFLICT (txid) DO NOTHING
        """
        
        values = []
        for tx in transactions:
            values.append((
                datetime.fromtimestamp(tx.get('timestamp', 0)) if tx.get('timestamp') else datetime.utcnow(),
                tx.get('txid'),
                tx.get('block_height'),
                float(tx.get('value_btc', 0)),
                tx.get('tier'),
                tx.get('flow_type'),
                float(tx.get('fee_btc', 0)),
                tx.get('input_count'),
                tx.get('output_count')
            ))
        
        try:
            with self.get_cursor() as cursor:
                execute_values(cursor, sql, values)
                saved = cursor.rowcount
            logger.debug("Whale transactions saved", count=saved)
            return saved
        except Exception as e:
            logger.error("Failed to save whale transactions", error=str(e))
            return 0
    
    # ========================================================
    # QUERY METHODS
    # ========================================================
    
    def get_latest_metrics(self, asset: str = 'BTC', 
                          timeframe: str = '1h') -> Optional[Dict[str, Any]]:
        """Get most recent metrics."""
        sql = """
        SELECT * FROM onchain_metrics 
        WHERE asset = %s AND timeframe = %s
        ORDER BY timestamp DESC LIMIT 1
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (asset, timeframe))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_metrics_history(self, asset: str = 'BTC', 
                           timeframe: str = '1h',
                           hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for specified period."""
        sql = """
        SELECT * FROM onchain_metrics 
        WHERE asset = %s AND timeframe = %s
          AND timestamp >= NOW() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (asset, timeframe, hours))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_signals(self, asset: str = 'BTC', 
                          timeframe: str = '1h') -> Optional[Dict[str, Any]]:
        """Get most recent signals."""
        sql = """
        SELECT * FROM onchain_signals 
        WHERE asset = %s AND timeframe = %s
        ORDER BY timestamp DESC LIMIT 1
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (asset, timeframe))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_signals_history(self, asset: str = 'BTC', 
                           timeframe: str = '1h',
                           hours: int = 24) -> List[Dict[str, Any]]:
        """Get signals history for specified period."""
        sql = """
        SELECT * FROM onchain_signals 
        WHERE asset = %s AND timeframe = %s
          AND timestamp >= NOW() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (asset, timeframe, hours))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_whale_activity_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get whale activity summary for specified period."""
        sql = """
        SELECT 
            COUNT(*) as total_whale_txs,
            SUM(value_btc) as total_volume_btc,
            AVG(value_btc) as avg_tx_value_btc,
            MAX(value_btc) as max_tx_value_btc,
            SUM(CASE WHEN flow_type = 'inflow' THEN value_btc ELSE 0 END) as inflow_btc,
            SUM(CASE WHEN flow_type = 'outflow' THEN value_btc ELSE 0 END) as outflow_btc,
            COUNT(CASE WHEN tier = 'whale' THEN 1 END) as whale_count,
            COUNT(CASE WHEN tier = 'ultra_whale' THEN 1 END) as ultra_whale_count,
            COUNT(CASE WHEN tier = 'leviathan' THEN 1 END) as leviathan_count
        FROM whale_transactions
        WHERE timestamp >= NOW() - INTERVAL '%s hours'
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (hours,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['net_flow_btc'] = (result.get('inflow_btc') or 0) - (result.get('outflow_btc') or 0)
                return result
            return {}
    
    def get_bias_distribution(self, hours: int = 24) -> Dict[str, int]:
        """Get distribution of bias values over time."""
        sql = """
        SELECT bias, COUNT(*) as count
        FROM onchain_signals
        WHERE timestamp >= NOW() - INTERVAL '%s hours'
        GROUP BY bias
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (hours,))
            return {row['bias']: row['count'] for row in cursor.fetchall()}
    
    def get_score_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get score statistics over time."""
        sql = """
        SELECT 
            AVG(onchain_score) as avg_score,
            MIN(onchain_score) as min_score,
            MAX(onchain_score) as max_score,
            STDDEV(onchain_score) as score_stddev,
            AVG(confidence) as avg_confidence,
            COUNT(*) as data_points
        FROM onchain_signals
        WHERE timestamp >= NOW() - INTERVAL '%s hours'
          AND onchain_score IS NOT NULL
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, (hours,))
            row = cursor.fetchone()
            return dict(row) if row else {}


# ========================================================
# Convenience Functions
# ========================================================

_db_instance: Optional[OnChainDatabase] = None


def get_database() -> OnChainDatabase:
    """Get or create database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = OnChainDatabase()
        _db_instance.ensure_tables()
    return _db_instance


def close_database():
    """Close database connections."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
