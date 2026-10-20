"""Spend-rate and progress signals.

Velocity alone is a poor loop detector: a legitimate batch job can spend fast,
and a loop with a small context can spend slowly. Pairing *how fast* money is
going out with *whether the agent is doing anything new* separates the two.

- SpendWindow: spend rate over a sliding time window.
- NoveltyTracker: fraction of distinct action fingerprints among the last N
  steps. An agent retrying the same call, or cycling between a few plans,
  drives this toward zero; an agent working through a queue stays near 1.
"""

from __future__ import annotations

from collections import deque
from typing import Optional


class SpendWindow:
    def __init__(self, window_s: float) -> None:
        self.window_s = window_s
        self._events: deque[tuple[float, int]] = deque()
        self._total = 0

    def add(self, t: float, amount: int) -> None:
        self._events.append((t, amount))
        self._total += amount

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._events and self._events[0][0] <= cutoff:
            _, a = self._events.popleft()
            self._total -= a

    def total(self, now: float) -> int:
        self._evict(now)
        return self._total

    def rate_per_min(self, now: float) -> float:
        """Micro-dollars per minute over the window."""
        return self.total(now) * 60.0 / self.window_s


class NoveltyTracker:
    def __init__(self, window: int = 20, min_samples: int = 10) -> None:
        self.min_samples = min_samples
        self._recent: deque[str] = deque(maxlen=window)

    def add(self, fingerprint: str) -> None:
        self._recent.append(fingerprint)

    def ratio(self) -> Optional[float]:
        if len(self._recent) < self.min_samples:
            return None
        return len(set(self._recent)) / len(self._recent)
