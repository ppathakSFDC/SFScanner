import asyncio
import time


class RateLimiter:
    """
    Async token-bucket rate limiter.
    Defaults to 80 calls/minute per org (stays under Salesforce's 100/min limit).
    """

    def __init__(self, calls_per_minute: int = 80):
        self.calls_per_minute = calls_per_minute
        self._tokens: float = float(calls_per_minute)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                float(self.calls_per_minute),
                self._tokens + elapsed * (self.calls_per_minute / 60.0),
            )
            self._last_refill = now

            if self._tokens < 1.0:
                wait_secs = (1.0 - self._tokens) * 60.0 / self.calls_per_minute
                await asyncio.sleep(wait_secs)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0
