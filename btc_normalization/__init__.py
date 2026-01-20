"""
Bitcoin Normalization Layer

Transforms raw UTXO/transaction data into time-series normalized features
for quantitative analysis and feature engineering.
"""

__version__ = "1.0.0"
__author__ = "Bitcoin Data Engineering Team"
__description__ = "Bitcoin on-chain data normalization pipeline"

from btc_normalization.core.normalizer import BitcoinNormalizer
from btc_normalization.core.aggregator import TimeSeriesAggregator
from btc_normalization.models.config import NormalizationConfig

__all__ = [
    "BitcoinNormalizer",
    "TimeSeriesAggregator", 
    "NormalizationConfig",
]