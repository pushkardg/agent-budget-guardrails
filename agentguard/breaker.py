"""Circuit breaker (closed -> open -> half-open -> closed)."""

from __future__ import annotations

from collections import deque


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, window_s: float = 60.0, cooldown_s: float = 120.0) -> None:
        self.failure_threshold = failure_threshold
        self.window_s = window_s
        self.cooldown_s = cooldown_s
        self.state = "closed"
        self._failures: deque[float] = deque()
        self._opened_at: float | None = None
        self._trial_out = False
        self.times_opened = 0

    def allow(self, now: float) -> bool:
        if self.state == "open":
            assert self._opened_at is not None
            if now - self._opened_at < self.cooldown_s:
                return False
            self.state = "half_open"
            self._trial_out = False
        if self.state == "half_open":
            if self._trial_out:
                return False
            self._trial_out = True
            return True
        return True

    def record_success(self, now: float) -> None:
        if self.state == "half_open":
            self.state = "closed"
        self._failures.clear()

    def record_failure(self, now: float) -> None:
        if self.state == "half_open":
            self._open(now)
            return
        self._failures.append(now)
        cutoff = now - self.window_s
        while self._failures and self._failures[0] <= cutoff:
            self._failures.popleft()
        if len(self._failures) >= self.failure_threshold:
            self._open(now)

    def _open(self, now: float) -> None:
        self.state = "open"
        self._opened_at = now
        self._failures.clear()
        self.times_opened += 1
