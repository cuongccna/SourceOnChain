"""Statistical utility functions for normalization."""

from decimal import Decimal
from typing import List, Dict, Any, Optional
import statistics
import numpy as np


def calculate_percentiles(values: List[Decimal], 
                        percentiles: List[float] = None) -> Dict[str, Decimal]:
    """
    Calculate percentiles for a list of values.
    
    Args:
        values: List of decimal values
        percentiles: List of percentiles to calculate (default: [10, 25, 50, 75, 90, 95, 99, 99.9])
        
    Returns:
        Dictionary mapping percentile names to values
    """
    if not values:
        return {}
    
    if percentiles is None:
        percentiles = [10, 25, 50, 75, 90, 95, 99, 99.9]
    
    # Convert to float for numpy operations
    float_values = [float(v) for v in values]
    sorted_values = sorted(float_values)
    
    result = {}
    for p in percentiles:
        # Use numpy percentile for accurate calculation
        percentile_value = np.percentile(sorted_values, p)
        
        # Format percentile key
        if p == int(p):
            key = f"p{int(p)}"
        else:
            key = f"p{int(p*10)}" if p < 10 else f"p{int(p*10)}"
        
        result[key] = Decimal(str(round(percentile_value, 8)))
    
    return result


def calculate_gini_coefficient(values: List[Decimal]) -> Decimal:
    """
    Calculate Gini coefficient for measuring inequality.
    
    Args:
        values: List of values to analyze
        
    Returns:
        Gini coefficient (0 = perfect equality, 1 = perfect inequality)
    """
    if not values or len(values) < 2:
        return Decimal('0')
    
    # Convert to float and sort
    sorted_values = sorted([float(v) for v in values])
    n = len(sorted_values)
    
    # Calculate Gini coefficient using the formula:
    # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    total_sum = sum(sorted_values)
    if total_sum == 0:
        return Decimal('0')
    
    weighted_sum = sum((i + 1) * value for i, value in enumerate(sorted_values))
    gini = (2 * weighted_sum) / (n * total_sum) - (n + 1) / n
    
    return Decimal(str(round(max(0, gini), 6)))


def calculate_statistical_measures(values: List[Decimal]) -> Dict[str, Decimal]:
    """
    Calculate comprehensive statistical measures for a dataset.
    
    Args:
        values: List of values to analyze
        
    Returns:
        Dictionary with statistical measures
    """
    if not values:
        return {
            'mean': Decimal('0'),
            'median': Decimal('0'),
            'std_dev': Decimal('0'),
            'skewness': Decimal('0'),
            'min': Decimal('0'),
            'max': Decimal('0'),
            'count': 0
        }
    
    float_values = [float(v) for v in values]
    
    # Basic statistics
    mean_val = statistics.mean(float_values)
    median_val = statistics.median(float_values)
    
    # Standard deviation
    std_dev = statistics.stdev(float_values) if len(float_values) > 1 else 0
    
    # Skewness calculation
    if len(float_values) > 2 and std_dev > 0:
        # Calculate skewness using the third moment
        mean_centered = [(x - mean_val) for x in float_values]
        third_moment = sum([(x ** 3) for x in mean_centered]) / len(float_values)
        skewness = third_moment / (std_dev ** 3)
    else:
        skewness = 0
    
    return {
        'mean': Decimal(str(round(mean_val, 8))),
        'median': Decimal(str(round(median_val, 8))),
        'std_dev': Decimal(str(round(std_dev, 8))),
        'skewness': Decimal(str(round(skewness, 6))),
        'min': Decimal(str(min(float_values))),
        'max': Decimal(str(max(float_values))),
        'count': len(values)
    }


def calculate_rolling_percentile(values: List[Decimal], percentile: float, 
                               window_size: int) -> List[Decimal]:
    """
    Calculate rolling percentile over a sliding window.
    
    Args:
        values: Time series values
        percentile: Percentile to calculate (0-100)
        window_size: Size of rolling window
        
    Returns:
        List of rolling percentile values
    """
    if len(values) < window_size:
        return []
    
    result = []
    float_values = [float(v) for v in values]
    
    for i in range(window_size - 1, len(float_values)):
        window = float_values[i - window_size + 1:i + 1]
        percentile_value = np.percentile(window, percentile)
        result.append(Decimal(str(round(percentile_value, 8))))
    
    return result


def detect_outliers_iqr(values: List[Decimal], 
                       multiplier: float = 1.5) -> Dict[str, Any]:
    """
    Detect outliers using Interquartile Range (IQR) method.
    
    Args:
        values: List of values to analyze
        multiplier: IQR multiplier for outlier detection (default: 1.5)
        
    Returns:
        Dictionary with outlier information
    """
    if len(values) < 4:
        return {
            'outliers': [],
            'outlier_count': 0,
            'outlier_ratio': 0,
            'lower_bound': None,
            'upper_bound': None
        }
    
    float_values = [float(v) for v in values]
    
    # Calculate quartiles
    q1 = np.percentile(float_values, 25)
    q3 = np.percentile(float_values, 75)
    iqr = q3 - q1
    
    # Calculate bounds
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr
    
    # Find outliers
    outliers = [v for v in values if float(v) < lower_bound or float(v) > upper_bound]
    
    return {
        'outliers': outliers,
        'outlier_count': len(outliers),
        'outlier_ratio': len(outliers) / len(values),
        'lower_bound': Decimal(str(round(lower_bound, 8))),
        'upper_bound': Decimal(str(round(upper_bound, 8))),
        'q1': Decimal(str(round(q1, 8))),
        'q3': Decimal(str(round(q3, 8))),
        'iqr': Decimal(str(round(iqr, 8)))
    }


def calculate_concentration_ratio(values: List[Decimal], 
                                top_n: int = 10) -> Decimal:
    """
    Calculate concentration ratio (percentage held by top N entities).
    
    Args:
        values: List of values (e.g., transaction amounts, balances)
        top_n: Number of top entities to consider
        
    Returns:
        Concentration ratio as decimal (0-1)
    """
    if not values or len(values) < top_n:
        return Decimal('0')
    
    sorted_values = sorted([float(v) for v in values], reverse=True)
    total_value = sum(sorted_values)
    
    if total_value == 0:
        return Decimal('0')
    
    top_n_value = sum(sorted_values[:top_n])
    concentration = top_n_value / total_value
    
    return Decimal(str(round(concentration, 6)))