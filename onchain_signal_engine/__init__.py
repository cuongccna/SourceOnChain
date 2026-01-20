"""
OnChain Signal & Score Engine

Production-grade signal generation system that transforms Bitcoin on-chain intelligence
into structured, verifiable signals with confidence scores for BotTrading systems.
"""

__version__ = "1.0.0"
__author__ = "OnChain Signal Engine Team"
__description__ = "Deterministic on-chain signal generation and scoring engine"

from onchain_signal_engine.core.signal_engine import OnChainSignalEngine
from onchain_signal_engine.core.score_calculator import ScoreCalculator
from onchain_signal_engine.models.config import SignalEngineConfig
from onchain_signal_engine.models.signal_data import SignalResult, OnChainScore

__all__ = [
    "OnChainSignalEngine",
    "ScoreCalculator", 
    "SignalEngineConfig",
    "SignalResult",
    "OnChainScore",
]