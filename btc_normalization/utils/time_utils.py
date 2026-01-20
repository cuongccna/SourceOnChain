"""Time utility functions for normalization pipeline."""

from datetime import datetime, timedelta, timezone
from typing import Tuple


def normalize_timestamp(timestamp: datetime, timeframe: str) -> datetime:
    """
    Normalize timestamp to timeframe boundary (candle open).
    
    Args:
        timestamp: Input timestamp
        timeframe: Target timeframe ('1h', '4h', '1d')
        
    Returns:
        Normalized timestamp at timeframe boundary
    """
    # Ensure UTC timezone
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    
    if timeframe == '1h':
        return timestamp.replace(minute=0, second=0, microsecond=0)
    
    elif timeframe == '4h':
        # Round down to nearest 4-hour boundary
        hour = (timestamp.hour // 4) * 4
        return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
    
    elif timeframe == '1d':
        # Round down to start of day (00:00 UTC)
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")


def get_timeframe_boundaries(timestamp: datetime, timeframe: str) -> Tuple[datetime, datetime]:
    """
    Get start and end boundaries for a timeframe period.
    
    Args:
        timestamp: Reference timestamp
        timeframe: Timeframe ('1h', '4h', '1d')
        
    Returns:
        Tuple of (start_time, end_time) for the timeframe period
    """
    start_time = normalize_timestamp(timestamp, timeframe)
    
    if timeframe == '1h':
        end_time = start_time + timedelta(hours=1)
    elif timeframe == '4h':
        end_time = start_time + timedelta(hours=4)
    elif timeframe == '1d':
        end_time = start_time + timedelta(days=1)
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    return start_time, end_time


def get_timeframe_duration_seconds(timeframe: str) -> int:
    """
    Get timeframe duration in seconds.
    
    Args:
        timeframe: Timeframe string ('1h', '4h', '1d')
        
    Returns:
        Duration in seconds
    """
    timeframe_map = {
        '1h': 3600,      # 1 hour
        '4h': 14400,     # 4 hours  
        '1d': 86400      # 24 hours
    }
    
    if timeframe not in timeframe_map:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    return timeframe_map[timeframe]


def generate_timeframe_range(start_time: datetime, end_time: datetime, 
                           timeframe: str) -> list[datetime]:
    """
    Generate a list of normalized timestamps for a timeframe range.
    
    Args:
        start_time: Start of range
        end_time: End of range
        timeframe: Timeframe ('1h', '4h', '1d')
        
    Returns:
        List of normalized timestamps
    """
    timestamps = []
    current_time = normalize_timestamp(start_time, timeframe)
    duration = timedelta(seconds=get_timeframe_duration_seconds(timeframe))
    
    while current_time < end_time:
        timestamps.append(current_time)
        current_time += duration
    
    return timestamps


def get_previous_timeframe_timestamp(timestamp: datetime, timeframe: str) -> datetime:
    """
    Get the previous timeframe timestamp.
    
    Args:
        timestamp: Current timestamp
        timeframe: Timeframe ('1h', '4h', '1d')
        
    Returns:
        Previous timeframe timestamp
    """
    current_normalized = normalize_timestamp(timestamp, timeframe)
    duration = timedelta(seconds=get_timeframe_duration_seconds(timeframe))
    
    return current_normalized - duration


def is_timeframe_complete(timestamp: datetime, timeframe: str, 
                         current_time: datetime = None) -> bool:
    """
    Check if a timeframe period is complete (past its end time).
    
    Args:
        timestamp: Timeframe timestamp to check
        timeframe: Timeframe ('1h', '4h', '1d')
        current_time: Current time (default: now)
        
    Returns:
        True if timeframe period is complete
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    start_time, end_time = get_timeframe_boundaries(timestamp, timeframe)
    return current_time >= end_time


def get_lookback_window(timestamp: datetime, window_hours: int) -> Tuple[datetime, datetime]:
    """
    Get lookback window boundaries for historical analysis.
    
    Args:
        timestamp: Reference timestamp
        window_hours: Lookback window in hours
        
    Returns:
        Tuple of (start_time, end_time) for lookback window
    """
    end_time = timestamp
    start_time = timestamp - timedelta(hours=window_hours)
    
    return start_time, end_time


def align_to_timeframe_grid(timestamp: datetime, base_timeframe: str, 
                          target_timeframe: str) -> datetime:
    """
    Align timestamp to a higher timeframe grid.
    
    Args:
        timestamp: Input timestamp
        base_timeframe: Base timeframe ('1h')
        target_timeframe: Target timeframe ('4h', '1d')
        
    Returns:
        Aligned timestamp
    """
    # Validate timeframe hierarchy
    hierarchy = {'1h': 1, '4h': 4, '1d': 24}
    
    if base_timeframe not in hierarchy or target_timeframe not in hierarchy:
        raise ValueError("Invalid timeframe")
    
    if hierarchy[base_timeframe] >= hierarchy[target_timeframe]:
        raise ValueError("Target timeframe must be higher than base timeframe")
    
    return normalize_timestamp(timestamp, target_timeframe)