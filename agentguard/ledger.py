"""Hierarchical spend ledger with reservations.

The core idea: an agent must *hold* budget before it acts, the same way a card
network places a hold before a charge settles. A step reserves its worst-case
cost (known input tokens + max output tokens), then settles the actual cost
when the model call returns.

Budgets form a tree: tenant -> root run -> child run -> ... A reservation must
fit at every level of the chain, so a run's budget covers all of its
descendants. That is what stops fan-out: per-run caps alone never see the
aggregate of a recursively spawning agent.

Production concerns this models (see tests):
- Concurrency: one lock makes check-and-hold atomic across the whole chain, so
  concurrent agents cannot jointly overshoot a budget. In a distributed store
  the equivalent is a single transaction (or keeping a whole run tree's
  counters in one partition).
- Crashes: a hold can carry a lease (ttl). If the caller dies before settling,
  sweep_expired() returns the money to the budget. If the call actually
  completed and a settle arrives late, the spend is still recorded (the money
  was really spent) and counted in late_settles for reconciliation against
  the provider's usage records.
- Caveat: expiry trades strict enforcement for liveness. If a lease expires
  while the call is in fact still running, its money can be re-reserved and
  total spend can exceed the limit. Keep leases longer than the provider's
  request deadline, renew() them while streaming, and alert on every expiry.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterator, Optional


class ReservationNotHeld(Exception):
    """A reservation ID was reused after its hold expired or was released.

    Returning the old reservation here would let the caller proceed with no
    money held, so the reuse is refused; the caller must reserve under a new ID.
    """


class BudgetExceeded(Exception):
    def __init__(self, key: str, requested: int, available: int):
        super().__init__(
            f"budget {key!r}: requested {requested} µ$, available {available} µ$"
        )
        self.key = key
        self.requested = requested
        self.available = available


@dataclass
class Budget:
    key: str
    limit: Optional[int]  # micro-dollars; None = unlimited
    parent: Optional[str]
    spent: int = 0
    reserved: int = 0

    def headroom(self) -> Optional[int]:
        if self.limit is None:
            return None
        return self.limit - self.spent - self.reserved


@dataclass
class Reservation:
    id: str
    key: str
    amount: int
    state: str = "held"  # held | settled | released | expired
    actual: Optional[int] = None
    expires_at: Optional[float] = None


class Ledger:
    def __init__(self) -> None:
        self.budgets: dict[str, Budget] = {}
        self.reservations: dict[str, Reservation] = {}
        self.overrun_micros = 0
        self.late_settles = 0  # settles that arrived after the hold expired or was released
        self._lock = threading.RLock()

    # -- structure -------------------------------------------------------
    def open(self, key: str, limit: Optional[int], parent: Optional[str] = None) -> Budget:
        if key in self.budgets:
            raise ValueError(f"budget {key!r} already exists")
        if parent is not None and parent not in self.budgets:
            raise KeyError(f"parent budget {parent!r} does not exist")
        b = Budget(key, limit, parent)
        self.budgets[key] = b
        return b

    def __contains__(self, key: str) -> bool:
        return key in self.budgets

    def chain(self, key: str) -> Iterator[Budget]:
        b: Optional[Budget] = self.budgets[key]
        while b is not None:
            yield b
            b = self.budgets[b.parent] if b.parent else None

    def headroom(self, key: str) -> Optional[int]:
        """Tightest headroom along the chain (None = unlimited)."""
        tight: Optional[int] = None
        for b in self.chain(key):
            h = b.headroom()
            if h is not None and (tight is None or h < tight):
                tight = h
        return tight

    def extend(self, key: str, delta: int) -> None:
        b = self.budgets[key]
        if b.limit is None:
            return
        b.limit += delta

    def spent(self, key: str) -> int:
        return self.budgets[key].spent

    # -- money movement --------------------------------------------------
    def reserve(self, key: str, amount: int, res_id: str,
                now: Optional[float] = None, ttl_s: Optional[float] = None) -> Reservation:
        """Hold `amount` at every level of the chain, or raise BudgetExceeded.

        Idempotent on res_id: retrying the same reservation returns the
        original hold (or the settled record) instead of double-reserving.
        Reusing an ID whose hold expired or was released raises
        ReservationNotHeld. With ttl_s (and now), the hold expires if not
        settled in time; see sweep_expired().
        """
        with self._lock:
            if res_id in self.reservations:
                r = self.reservations[res_id]
                if r.state in ("expired", "released"):
                    raise ReservationNotHeld(f"reservation {res_id} is {r.state}; reserve under a new ID")
                return r
            if amount < 0:
                raise ValueError("reservation amount must be non-negative")
            chain = list(self.chain(key))
            for b in chain:
                h = b.headroom()
                if h is not None and h < amount:
                    raise BudgetExceeded(b.key, amount, h)
            for b in chain:
                b.reserved += amount
            expires = None if ttl_s is None or now is None else now + ttl_s
            r = Reservation(res_id, key, amount, expires_at=expires)
            self.reservations[res_id] = r
            return r

    def settle(self, res_id: str, actual: int) -> bool:
        """Convert a hold into spend. Returns False if already settled (idempotent).

        A settle for a hold that already expired or was released still records
        the spend: the provider call happened and was billed. It is counted in
        late_settles so reconciliation can look at it.
        """
        with self._lock:
            r = self.reservations[res_id]
            if r.state == "settled":
                return False
            held = r.state == "held"
            for b in self.chain(r.key):
                if held:
                    b.reserved -= r.amount
                b.spent += actual
            if not held:
                self.late_settles += 1
            if actual > r.amount:
                self.overrun_micros += actual - r.amount
            r.state = "settled"
            r.actual = actual
            return True

    def release(self, res_id: str) -> bool:
        with self._lock:
            r = self.reservations[res_id]
            if r.state != "held":
                return False
            for b in self.chain(r.key):
                b.reserved -= r.amount
            r.state = "released"
            return True

    def renew(self, res_id: str, now: float, ttl_s: float) -> bool:
        """Extend a held reservation's lease (call still in flight). False if not held."""
        with self._lock:
            r = self.reservations[res_id]
            if r.state != "held":
                return False
            r.expires_at = now + ttl_s
            return True

    def sweep_expired(self, now: float) -> list[str]:
        """Return expired holds to their budgets (caller crashed or hung)."""
        out = []
        with self._lock:
            for r in self.reservations.values():
                if r.state == "held" and r.expires_at is not None and now >= r.expires_at:
                    for b in self.chain(r.key):
                        b.reserved -= r.amount
                    r.state = "expired"
                    out.append(r.id)
        return out
