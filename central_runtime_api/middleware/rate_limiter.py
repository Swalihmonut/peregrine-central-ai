"""Sliding-window in-memory rate limiter and concurrency guard."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple


class RateLimiter:
    """Thread-safe sliding-window rate limiter per client key."""

    def __init__(self, requests_per_minute: int = 60, max_concurrency: int = 10, enabled: bool = True):
        self.rpm = requests_per_minute
        self.max_concurrency = max_concurrency
        self.enabled = enabled
        self._lock = threading.Lock()
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._active_concurrency: Dict[str, int] = defaultdict(int)

    def acquire(self, client_key: str) -> Tuple[bool, int, float, str]:
        """Attempt to acquire a request slot.
        
        Returns:
            (allowed: bool, remaining_requests: int, reset_after_seconds: float, reason: str)
        """
        if not self.enabled:
            return True, self.rpm, 0.0, "rate_limiting_disabled"

        now = time.time()
        window_start = now - 60.0

        with self._lock:
            # Clean expired timestamps outside 60-second window
            req_history = [t for t in self._requests[client_key] if t > window_start]
            self._requests[client_key] = req_history

            # Check concurrency limit
            if self._active_concurrency[client_key] >= self.max_concurrency:
                return False, 0, 1.0, "MAX_CONCURRENCY_EXCEEDED"

            # Check RPM window limit
            if len(req_history) >= self.rpm:
                oldest = req_history[0]
                reset_after = max(0.1, round(60.0 - (now - oldest), 2))
                return False, 0, reset_after, "RATE_LIMIT_EXCEEDED"

            # Record request
            self._requests[client_key].append(now)
            self._active_concurrency[client_key] += 1
            remaining = max(0, self.rpm - len(self._requests[client_key]))
            return True, remaining, 60.0, "OK"

    def release(self, client_key: str):
        """Release active concurrency slot upon request completion."""
        if not self.enabled:
            return
        with self._lock:
            if self._active_concurrency[client_key] > 0:
                self._active_concurrency[client_key] -= 1
