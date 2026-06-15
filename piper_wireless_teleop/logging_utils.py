"""Rate-limited status printing for scripts.

Robot control loops can run at tens of hertz while human-readable status only
needs to print occasionally. This module keeps logging from becoming a source of
latency or terminal noise.
"""

from __future__ import annotations

import time


class RateLimitedPrinter:
    """Print messages no faster than ``rate_hz`` unless forced."""

    def __init__(self, rate_hz: float) -> None:
        self.interval_s = 1.0 / rate_hz if rate_hz > 0 else float("inf")
        self._last_print = 0.0

    def print(self, message: str, *, force: bool = False) -> None:
        """Print ``message`` if enough time has elapsed."""

        now = time.monotonic()
        if force or now - self._last_print >= self.interval_s:
            print(message, flush=True)
            self._last_print = now
