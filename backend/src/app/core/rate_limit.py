from __future__ import annotations

from datetime import date

from src.app.config import settings
from src.app.infrastructure.rate_limit_db import (
    get_daily_interaction_count,
    increment_interaction_count,
)


class RateLimitExceeded(Exception):
    """Raised when the daily interaction limit is exceeded."""
    
    def __init__(self, identifier: str, current_count: int, limit: int):
        self.identifier = identifier
        self.current_count = current_count
        self.limit = limit
        super().__init__(
            f"Daily interaction limit exceeded: {current_count}/{limit} for identifier {identifier}"
        )


def check_rate_limit(identifier: str, daily_limit: int) -> None:
    """
    Check if the identifier has exceeded the daily interaction limit.
    
    Raises RateLimitExceeded if the limit is exceeded.
    
    Args:
        identifier: IP address or user ID
        daily_limit: Maximum allowed interactions per day
        
    Raises:
        RateLimitExceeded: If the limit is exceeded
    """
    current_count = get_daily_interaction_count(identifier)
    
    if current_count >= daily_limit:
        raise RateLimitExceeded(identifier, current_count, daily_limit)


def record_interaction(identifier: str) -> int:
    """
    Record a new interaction and return the updated count.
    
    Args:
        identifier: IP address or user ID
        
    Returns:
        New interaction count after increment
    """
    return increment_interaction_count(identifier)


def get_remaining_interactions(identifier: str, daily_limit: int) -> int:
    """
    Get the number of remaining interactions for today.
    
    Args:
        identifier: IP address or user ID
        daily_limit: Maximum allowed interactions per day
        
    Returns:
        Number of remaining interactions (can be negative if limit exceeded)
    """
    current_count = get_daily_interaction_count(identifier)
    return max(0, daily_limit - current_count)

