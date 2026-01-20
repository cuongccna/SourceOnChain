"""Behavioral pattern detection utilities for whale analysis."""

from decimal import Decimal
from typing import List, Tuple, Dict, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class PatternResult:
    """Result of behavioral pattern detection."""
    pattern_detected: bool
    pattern_strength: float  # 0-1 scale
    confidence_score: float  # 0-1 scale
    streak_length: int
    supporting_evidence: Dict[str, bool]


def detect_accumulation_pattern(whale_net_flow: List[Decimal],
                               whale_ratio: List[Decimal],
                               min_periods: int = 3,
                               flow_threshold: Decimal = Decimal('0')) -> PatternResult:
    """
    Detect whale accumulation pattern.
    
    Args:
        whale_net_flow: Series of whale net flow values (created - spent)
        whale_ratio: Series of whale transaction ratios
        min_periods: Minimum periods for pattern detection
        flow_threshold: Minimum net flow threshold
        
    Returns:
        PatternResult with accumulation analysis
    """
    if len(whale_net_flow) < min_periods or len(whale_ratio) < min_periods:
        return PatternResult(
            pattern_detected=False,
            pattern_strength=0.0,
            confidence_score=0.0,
            streak_length=0,
            supporting_evidence={}
        )
    
    # Analyze recent periods
    recent_flow = whale_net_flow[-min_periods:]
    recent_ratio = whale_ratio[-min_periods:]
    
    # Evidence 1: Positive net flow
    positive_flow_periods = sum(1 for f in recent_flow if f > flow_threshold)
    positive_flow_ratio = positive_flow_periods / len(recent_flow)
    
    # Evidence 2: Increasing whale ratio trend
    ratio_trend_strength = calculate_trend_strength([float(r) for r in recent_ratio])
    increasing_ratio = ratio_trend_strength > 0.1
    
    # Evidence 3: Consistent accumulation (no major distribution periods)
    consistent_accumulation = all(f >= -abs(flow_threshold) for f in recent_flow)
    
    # Evidence 4: Volume trend (if whale ratio increasing, volume should be meaningful)
    volume_meaningful = recent_ratio[-1] > Decimal('0.01')  # At least 1% of volume
    
    # Calculate streak length
    streak_length = 0
    for i in range(len(whale_net_flow) - 1, -1, -1):
        if whale_net_flow[i] > flow_threshold:
            streak_length += 1
        else:
            break
    
    # Supporting evidence
    supporting_evidence = {
        'positive_flow': positive_flow_ratio >= 0.6,  # 60% of periods positive
        'increasing_ratio': increasing_ratio,
        'consistent_pattern': consistent_accumulation,
        'meaningful_volume': volume_meaningful,
        'extended_streak': streak_length >= min_periods
    }
    
    # Pattern detection logic
    pattern_detected = (
        supporting_evidence['positive_flow'] and
        supporting_evidence['increasing_ratio'] and
        supporting_evidence['consistent_pattern']
    )
    
    # Calculate pattern strength
    evidence_count = sum(supporting_evidence.values())
    pattern_strength = evidence_count / len(supporting_evidence)
    
    # Calculate confidence score
    confidence_factors = [
        min(1.0, positive_flow_ratio),  # Flow consistency
        min(1.0, max(0.0, ratio_trend_strength * 2)),  # Ratio trend strength
        min(1.0, streak_length / (min_periods * 2)),  # Streak persistence
        1.0 if volume_meaningful else 0.5  # Volume significance
    ]
    confidence_score = np.mean(confidence_factors)
    
    return PatternResult(
        pattern_detected=pattern_detected,
        pattern_strength=pattern_strength,
        confidence_score=confidence_score,
        streak_length=streak_length,
        supporting_evidence=supporting_evidence
    )


def detect_distribution_pattern(whale_net_flow: List[Decimal],
                               whale_ratio: List[Decimal],
                               min_periods: int = 3,
                               flow_threshold: Decimal = Decimal('0')) -> PatternResult:
    """
    Detect whale distribution pattern.
    
    Args:
        whale_net_flow: Series of whale net flow values (created - spent)
        whale_ratio: Series of whale transaction ratios
        min_periods: Minimum periods for pattern detection
        flow_threshold: Minimum net flow threshold (negative for distribution)
        
    Returns:
        PatternResult with distribution analysis
    """
    if len(whale_net_flow) < min_periods or len(whale_ratio) < min_periods:
        return PatternResult(
            pattern_detected=False,
            pattern_strength=0.0,
            confidence_score=0.0,
            streak_length=0,
            supporting_evidence={}
        )
    
    # Analyze recent periods
    recent_flow = whale_net_flow[-min_periods:]
    recent_ratio = whale_ratio[-min_periods:]
    
    # Evidence 1: Negative net flow (distribution)
    negative_flow_periods = sum(1 for f in recent_flow if f < -abs(flow_threshold))
    negative_flow_ratio = negative_flow_periods / len(recent_flow)
    
    # Evidence 2: Increasing whale ratio (more whale activity during distribution)
    ratio_trend_strength = calculate_trend_strength([float(r) for r in recent_ratio])
    increasing_ratio = ratio_trend_strength > 0.1
    
    # Evidence 3: Consistent distribution pattern
    consistent_distribution = all(f <= abs(flow_threshold) for f in recent_flow)
    
    # Evidence 4: Significant whale activity volume
    volume_meaningful = recent_ratio[-1] > Decimal('0.02')  # At least 2% for distribution
    
    # Calculate distribution streak length
    streak_length = 0
    for i in range(len(whale_net_flow) - 1, -1, -1):
        if whale_net_flow[i] < -abs(flow_threshold):
            streak_length += 1
        else:
            break
    
    # Supporting evidence
    supporting_evidence = {
        'negative_flow': negative_flow_ratio >= 0.6,  # 60% of periods negative
        'increasing_ratio': increasing_ratio,
        'consistent_pattern': consistent_distribution,
        'meaningful_volume': volume_meaningful,
        'extended_streak': streak_length >= min_periods
    }
    
    # Pattern detection logic
    pattern_detected = (
        supporting_evidence['negative_flow'] and
        supporting_evidence['increasing_ratio'] and
        supporting_evidence['consistent_pattern']
    )
    
    # Calculate pattern strength
    evidence_count = sum(supporting_evidence.values())
    pattern_strength = evidence_count / len(supporting_evidence)
    
    # Calculate confidence score
    confidence_factors = [
        min(1.0, negative_flow_ratio),  # Flow consistency
        min(1.0, max(0.0, ratio_trend_strength * 2)),  # Ratio trend strength
        min(1.0, streak_length / (min_periods * 2)),  # Streak persistence
        1.0 if volume_meaningful else 0.5  # Volume significance
    ]
    confidence_score = np.mean(confidence_factors)
    
    return PatternResult(
        pattern_detected=pattern_detected,
        pattern_strength=pattern_strength,
        confidence_score=confidence_score,
        streak_length=streak_length,
        supporting_evidence=supporting_evidence
    )


def calculate_pattern_strength(values: List[float], 
                             pattern_type: str = 'trend') -> float:
    """
    Calculate strength of a pattern in time series data.
    
    Args:
        values: Time series values
        pattern_type: Type of pattern ('trend', 'spike', 'volatility')
        
    Returns:
        Pattern strength (0-1 scale)
    """
    if len(values) < 3:
        return 0.0
    
    if pattern_type == 'trend':
        return calculate_trend_strength_normalized(values)
    elif pattern_type == 'spike':
        return calculate_spike_strength(values)
    elif pattern_type == 'volatility':
        return calculate_volatility_strength(values)
    else:
        return 0.0


def calculate_trend_strength_normalized(values: List[float]) -> float:
    """Calculate normalized trend strength (0-1 scale)."""
    if len(values) < 3:
        return 0.0
    
    try:
        # Linear regression
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = np.polyfit(x, values, 1, full=True)[:5]
        
        # Normalize by value range and correlation
        value_range = max(values) - min(values)
        if value_range == 0:
            return 0.0
        
        # Trend strength = normalized_slope * r_squared
        normalized_slope = abs(slope * len(values)) / value_range
        trend_strength = min(1.0, normalized_slope * (r_value ** 2))
        
        return trend_strength
        
    except Exception:
        return 0.0


def calculate_spike_strength(values: List[float]) -> float:
    """Calculate spike strength based on z-score of recent values."""
    if len(values) < 5:
        return 0.0
    
    try:
        # Use last value as potential spike
        recent_value = values[-1]
        historical_values = values[:-1]
        
        mean_val = np.mean(historical_values)
        std_val = np.std(historical_values)
        
        if std_val == 0:
            return 0.0
        
        z_score = abs(recent_value - mean_val) / std_val
        
        # Convert z-score to 0-1 scale (z-score of 3 = strength of 1)
        spike_strength = min(1.0, z_score / 3.0)
        
        return spike_strength
        
    except Exception:
        return 0.0


def calculate_volatility_strength(values: List[float]) -> float:
    """Calculate volatility strength based on coefficient of variation."""
    if len(values) < 3:
        return 0.0
    
    try:
        mean_val = np.mean(values)
        if mean_val == 0:
            return 0.0
        
        std_val = np.std(values)
        cv = std_val / mean_val
        
        # Convert CV to 0-1 scale (CV of 1 = strength of 1)
        volatility_strength = min(1.0, cv)
        
        return volatility_strength
        
    except Exception:
        return 0.0


def detect_behavioral_regime_shift(whale_ratios: List[Decimal],
                                 window_size: int = 14,
                                 shift_threshold: float = 0.5) -> Tuple[bool, float]:
    """
    Detect behavioral regime shift in whale activity patterns.
    
    Args:
        whale_ratios: Series of whale transaction ratios
        window_size: Window size for regime comparison
        shift_threshold: Threshold for detecting significant shift
        
    Returns:
        Tuple of (shift_detected, shift_magnitude)
    """
    if len(whale_ratios) < window_size * 2:
        return False, 0.0
    
    try:
        # Compare recent window to previous window
        recent_window = [float(r) for r in whale_ratios[-window_size:]]
        previous_window = [float(r) for r in whale_ratios[-window_size*2:-window_size]]
        
        recent_mean = np.mean(recent_window)
        previous_mean = np.mean(previous_window)
        
        if previous_mean == 0:
            return False, 0.0
        
        # Calculate relative change
        relative_change = abs(recent_mean - previous_mean) / previous_mean
        
        shift_detected = relative_change > shift_threshold
        shift_magnitude = min(1.0, relative_change)
        
        return shift_detected, shift_magnitude
        
    except Exception:
        return False, 0.0


def calculate_behavioral_consistency(pattern_flags: List[bool],
                                   min_consistency: float = 0.7) -> Tuple[bool, float]:
    """
    Calculate consistency of behavioral patterns.
    
    Args:
        pattern_flags: Series of boolean pattern flags
        min_consistency: Minimum consistency threshold
        
    Returns:
        Tuple of (is_consistent, consistency_score)
    """
    if len(pattern_flags) == 0:
        return False, 0.0
    
    # Calculate consistency as ratio of True flags
    consistency_score = sum(pattern_flags) / len(pattern_flags)
    is_consistent = consistency_score >= min_consistency
    
    return is_consistent, consistency_score