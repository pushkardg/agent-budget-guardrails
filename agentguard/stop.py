"""Cooperative stop signals.

GRACEFUL: the agent stops at its next safe point. A tool call that has staged
a side effect but not committed it is compensated (rolled back), so nothing is
left half-applied, and the run's last checkpoint stays valid for resume.

HARD: the process is killed wherever it is. Whatever was staged stays staged.
This is what an external watchdog or `kill -9` does.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StopMode(Enum):
    GRACEFUL = "graceful"
    HARD = "hard"


@dataclass
class StopRequest:
    reason: str
    mode: StopMode
    at: float


class StopToken:
    def __init__(self) -> None:
        self._request: Optional[StopRequest] = None

    @property
    def requested(self) -> Optional[StopRequest]:
        return self._request

    def request(self, reason: str, mode: StopMode, at: float) -> None:
        # First request wins; a later, softer request must not downgrade a hard stop.
        if self._request is None:
            self._request = StopRequest(reason, mode, at)
