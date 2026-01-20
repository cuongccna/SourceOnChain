"""Time utility functions for blockchain data."""

from datetime import datetime, timezone
from typing import Union
import structlog

logger = structlog.get_logger(__name__)


def to_utc_timestamp(timestamp: Union[int, float, datetime]) -> datetime:
    """Convert various timestamp formats to UTC datetime."""
    if isinstance(timestamp, datetime):
        # Ensure timezone awareness
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
    
    elif isinstance(timestamp, (int, float)):
        # Unix timestamp
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    else:
        raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")


def format_block_time(block_time: Union[int, datetime]) -> datetime:
    """Format block time to UTC datetime."""
    return to_utc_timestamp(block_time)


def get_current_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def timestamp_to_unix(dt: datetime) -> int:
    """Convert datetime to Unix timestamp."""
    return int(dt.timestamp())


def unix_to_timestamp(unix_time: int) -> datetime:
    """Convert Unix timestamp to UTC datetime."""
    return datetime.fromtimestamp(unix_time, tz=timezone.utc)