"""Rate limiting utility for API endpoints."""

import time
from typing import Dict, Tuple
from collections import defaultdict, deque


class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client."""
        
        now = time.time()
        client_requests = self.requests[client_id]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) < self.max_requests:
            client_requests.append(now)
            return True
        
        return False
    
    def get_remaining(self, client_id: str) -> Tuple[int, int]:
        """Get remaining requests and reset time."""
        
        now = time.time()
        client_requests = self.requests[client_id]
        
        # Remove old requests
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        remaining = max(0, self.max_requests - len(client_requests))
        reset_time = int(client_requests[0] + self.window_seconds) if client_requests else int(now)
        
        return remaining, reset_time