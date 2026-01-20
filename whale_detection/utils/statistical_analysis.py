"""Statistical analysis utilities for whale detection."""

from decimal import Decimal
from typing import List, Dict, Tuple, Optional
import numpy as np
import scipy.stats as stats
from dataclasses import dataclass


@dataclass
class RollingPercentileResult:
    """Result of rolling percentile calculation."""
    percentiles: Dict[str, List[Decimal]]
    sample_sizes: List[int]
    stability_scores: List[float]
    regime_changes: List[bool]


def calculate_rolling_percentiles(values: List[Decimal], 
                                window_size: int,
                                percentiles: List[float] = None) -> RollingPercentileResult:
    """
    Calculate rolling percentiles with stability analysis.
    
    Args:
        values: Time series of transaction values
        window_size: Rolling window size
        percentiles: Percentiles to calculate (default: [95, 99, 99.9, 99.99])
        
    Returns:
        RollingPercentileResult with percentiles and stability metrics
    """
    if percentiles is None:
        percentiles = [95.0, 99.0, 99.9, 99.99]
    
    if len(values) < window_size:
        return RollingPercentileResult(
            percentiles={},
            sample_sizes=[],
            stability_scores=[],
            regime_changes=[]
        )
    
    float_values = [float(v) for v in values]
    result_percentiles = {f"p{int(p*10) if p < 10 else int(p)}": [] for p in percentiles}
    sample_sizes = []
    stability_scores = []
    regime_changes = []
    
    # Calculate rolling percentiles
    for i in range(window_size - 1, len(float_values)):
        window = float_values[i - window_size + 1:i + 1]
        
        # Calculate percentiles for this window
        window_percentiles = {}
        for p in percentiles:
            percentile_value = np.percentile(window, p)
            key = f"p{int(p*10) if p < 10 else int(p)}"
            window_percentiles[key] = Decimal(str(round(percentile_value, 8)))
            result_percentiles[key].append(window_percentiles[key])
        
        sample_sizes.append(len(window))
        
        # Calculate stability score (coefficient of variation of recent percentiles)
        if len(result_percentiles['p99']) >= 10:  # Need at least 10 periods
            recent_p99 = [float(p) for p in result_percentiles['p99'][-10:]]
            cv = np.std(recent_p99) / np.mean(recent_p99) if np.mean(recent_p99) > 0 else 0
            stability_score = max(0, 1 - cv)  # Higher = more stable
            stability_scores.append(stability_score)
        else:
            stability_scores.append(1.0)
        
        # Detect regime change
        if len(result_percentiles['p99']) >= 30:  # Need sufficient history
            regime_change = detect_regime_change(
                current_threshold=window_percentiles['p99'],
                historical_thresholds=result_percentiles['p99'][-30:-1]
            )
            regime_changes.append(regime_change)
        else:
            regime_changes.append(False)
    
    return RollingPercentileResult(
        percentiles=result_percentiles,
        sample_sizes=sample_sizes,
        stability_scores=stability_scores,
        regime_changes=regime_changes
    )


def detect_activity_spikes(activity_counts: List[int], 
                          z_threshold: float = 2.0) -> Tuple[List[bool], List[float]]:
    """
    Detect activity spikes using z-score analysis.
    
    Args:
        activity_counts: Time series of activity counts
        z_threshold: Z-score threshold for spike detection
        
    Returns:
        Tuple of (spike_flags, z_scores)
    """
    if len(activity_counts) < 10:
        return [False] * len(activity_counts), [0.0] * len(activity_counts)
    
    spike_flags = []
    z_scores = []
    
    # Calculate rolling z-scores
    for i in range(len(activity_counts)):
        if i < 9:  # Need at least 10 periods for meaningful z-score
            spike_flags.append(False)
            z_scores.append(0.0)
            continue
        
        # Use last 30 periods for z-score calculation (or all available if less)
        lookback_start = max(0, i - 29)
        historical_counts = activity_counts[lookback_start:i]
        current_count = activity_counts[i]
        
        if len(historical_counts) == 0:
            spike_flags.append(False)
            z_scores.append(0.0)
            continue
        
        mean_count = np.mean(historical_counts)
        std_count = np.std(historical_counts)
        
        if std_count == 0:
            z_score = 0.0
        else:
            z_score = (current_count - mean_count) / std_count
        
        z_scores.append(z_score)
        spike_flags.append(abs(z_score) > z_threshold)
    
    return spike_flags, z_scores


def calculate_trend_strength(values: List[Decimal], 
                           min_periods: int = 3) -> float:
    """
    Calculate trend strength using linear regression.
    
    Args:
        values: Time series values
        min_periods: Minimum periods required
        
    Returns:
        Trend strength (-1 to 1, where 1 = strong uptrend, -1 = strong downtrend)
    """
    if len(values) < min_periods:
        return 0.0
    
    float_values = [float(v) for v in values]
    x = np.arange(len(float_values))
    
    try:
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, float_values)
        
        # Normalize slope by value range to get strength (-1 to 1)
        value_range = max(float_values) - min(float_values)
        if value_range == 0:
            return 0.0
        
        # Trend strength = (slope * periods) / value_range * r_squared
        trend_strength = (slope * len(float_values)) / value_range * (r_value ** 2)
        
        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, trend_strength))
        
    except Exception:
        return 0.0


def detect_regime_change(current_threshold: Decimal,
                        historical_thresholds: List[Decimal],
                        sensitivity: float = 2.0) -> bool:
    """
    Detect regime change in whale thresholds.
    
    Args:
        current_threshold: Current threshold value
        historical_thresholds: Historical threshold values
        sensitivity: Z-score sensitivity for detection
        
    Returns:
        True if regime change detected
    """
    if len(historical_thresholds) < 10:
        return False
    
    historical_values = [float(t) for t in historical_thresholds]
    current_value = float(current_threshold)
    
    mean_threshold = np.mean(historical_values)
    std_threshold = np.std(historical_values)
    
    if std_threshold == 0:
        return False
    
    z_score = abs(current_value - mean_threshold) / std_threshold
    
    return z_score > sensitivity


def calculate_percentile_stability(percentile_series: List[Decimal],
                                 window_size: int = 10) -> float:
    """
    Calculate stability of percentile series using coefficient of variation.
    
    Args:
        percentile_series: Series of percentile values
        window_size: Window for stability calculation
        
    Returns:
        Stability score (0-1, higher = more stable)
    """
    if len(percentile_series) < window_size:
        return 1.0
    
    recent_values = [float(p) for p in percentile_series[-window_size:]]
    
    mean_value = np.mean(recent_values)
    if mean_value == 0:
        return 1.0
    
    std_value = np.std(recent_values)
    cv = std_value / mean_value
    
    # Convert CV to stability score (lower CV = higher stability)
    stability_score = 1 / (1 + cv)
    
    return min(1.0, stability_score)


def calculate_distribution_metrics(values: List[Decimal]) -> Dict[str, float]:
    """
    Calculate distribution metrics for whale threshold validation.
    
    Args:
        values: Distribution values
        
    Returns:
        Dictionary with distribution metrics
    """
    if len(values) < 10:
        return {
            'skewness': 0.0,
            'kurtosis': 0.0,
            'normality_p_value': 1.0
        }
    
    float_values = [float(v) for v in values]
    
    try:
        # Calculate skewness and kurtosis
        skewness = stats.skew(float_values)
        kurtosis = stats.kurtosis(float_values)
        
        # Test for normality (Shapiro-Wilk test)
        if len(float_values) <= 5000:  # Shapiro-Wilk has sample size limit
            _, normality_p = stats.shapiro(float_values)
        else:
            # Use Kolmogorov-Smirnov test for large samples
            _, normality_p = stats.kstest(float_values, 'norm')
        
        return {
            'skewness': float(skewness),
            'kurtosis': float(kurtosis),
            'normality_p_value': float(normality_p)
        }
        
    except Exception:
        return {
            'skewness': 0.0,
            'kurtosis': 0.0,
            'normality_p_value': 1.0
        }


def validate_threshold_quality(thresholds: Dict[str, List[Decimal]],
                              min_stability: float = 0.7) -> Dict[str, bool]:
    """
    Validate quality of calculated thresholds.
    
    Args:
        thresholds: Dictionary of threshold series
        min_stability: Minimum stability score required
        
    Returns:
        Dictionary of quality flags for each threshold
    """
    quality_flags = {}
    
    for threshold_name, threshold_series in thresholds.items():
        if len(threshold_series) < 10:
            quality_flags[threshold_name] = False
            continue
        
        # Calculate stability
        stability = calculate_percentile_stability(threshold_series)
        
        # Check for reasonable values (not all zeros, not extreme outliers)
        float_values = [float(t) for t in threshold_series[-10:]]
        has_variation = np.std(float_values) > 0
        no_extreme_outliers = all(v < np.mean(float_values) * 10 for v in float_values)
        
        quality_flags[threshold_name] = (
            stability >= min_stability and
            has_variation and
            no_extreme_outliers
        )
    
    return quality_flags