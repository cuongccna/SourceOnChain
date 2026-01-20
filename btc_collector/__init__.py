"""
Bitcoin Raw Data Collector

A production-ready Bitcoin blockchain data collector using only free, self-hosted data sources.
Designed for quantitative crypto research and bot trading systems.
"""

__version__ = "1.0.0"
__author__ = "Bitcoin Data Engineering Team"
__description__ = "Raw on-chain data collector for Bitcoin using Bitcoin Core RPC"

from btc_collector.core.collector import BitcoinCollector
from btc_collector.core.rpc_client import BitcoinRPCClient
from btc_collector.database.manager import DatabaseManager
from btc_collector.models.config import CollectorConfig

__all__ = [
    "BitcoinCollector",
    "BitcoinRPCClient", 
    "DatabaseManager",
    "CollectorConfig",
]