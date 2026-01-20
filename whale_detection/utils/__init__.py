"""Utility functions for whale detection pipeline."""

from whale_detection.utils.statistical_analysis import (
    calculate_rolling_percentiles,
    detect_activity_spikes,
    calculate_trend_strength,
    detect_regime_change
)
from whale_detection.utils.behavioral_patterns import (
    detect_accumulation_pattern,
    detect_distribution_pattern,
    calculate_pattern_strength
)

__all__ = [
    "calculate_rolling_percentiles",
    "detect_activity_spikes",
    "calculate_trend_strength",
    "detect_regime_change",
    "detect_accumulation_pattern",
    "detect_distribution_pattern",
    "calculate_pattern_strength",
]