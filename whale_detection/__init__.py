"""
Bitcoin Whale Detection Engine

Statistical whale detection using dynamic percentile thresholds
and on-chain behavioral pattern analysis.
"""

__version__ = "1.0.0"
__author__ = "Bitcoin Whale Detection Team"
__description__ = "Statistical whale detection engine for Bitcoin on-chain analysis"

from whale_detection.core.whale_detector import WhaleDetector
from whale_detection.core.threshold_calculator import ThresholdCalculator
from whale_detection.models.config import WhaleDetectionConfig

__all__ = [
    "WhaleDetector",
    "ThresholdCalculator",
    "WhaleDetectionConfig",
]