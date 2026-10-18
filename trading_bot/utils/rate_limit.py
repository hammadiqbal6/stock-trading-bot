"""Simple token-bucket rate limiter for external APIs."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


class RateLimitError(Exception):
    """Raised when a caller should back off."""

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimiter:
    """Thread-safe token bucket.

    Parameters
    ----------
    rate:
        Tokens added per second.
    capacity:
        Maximum burst size.
    name:
        Identifier for error messages / logs.
    """

    rate: float
    capacity: float
    name: str = "api"
    _tokens: float = 0.0
    _updated: float = 0.0
    _lock: threading.Lock | None = None

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0, *, block: bool = True, timeout: float = 30.0) -> None:
        assert self._lock is not None
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._updated
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self.rate if self.rate > 0 else timeout
            if not block:
                raise RateLimitError(
                    f"Rate limit exceeded for {self.name}; retry after {wait:.2f}s",
                    retry_after=wait,
                )
            if time.monotonic() + wait > deadline:
                raise RateLimitError(
                    f"Timed out waiting for {self.name} rate limit ({wait:.2f}s needed)",
                    retry_after=wait,
                )
            time.sleep(min(wait, 0.25))
