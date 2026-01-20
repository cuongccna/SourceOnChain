"""
Smart Wallet Classification Engine

Behavioral classification of Bitcoin addresses using on-chain historical data.
Classifies wallets into SMART_MONEY, NEUTRAL_CAPITAL, DUMB_MONEY based on
consistent profitable behavior patterns.
"""

__version__ = "1.0.0"
__author__ = "Smart Wallet Classification Team"
__description__ = "Behavioral wallet classification engine for Bitcoin on-chain analysis"

from smart_wallet_classifier.core.classifier import SmartWalletClassifier
from smart_wallet_classifier.core.feature_engine import FeatureEngine
from smart_wallet_classifier.models.config import SmartWalletConfig

__all__ = [
    "SmartWalletClassifier",
    "FeatureEngine",
    "SmartWalletConfig",
]