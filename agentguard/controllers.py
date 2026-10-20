"""Guardrail strategies compared in the benchmark.

- NoGuard:            nothing; spend is only observed.
- MonthlyBudgetAlert: the common default. Alert when the tenant crosses a
                      percentage of its monthly budget, as seen through a
                      billing/usage pipeline with reporting delay. Never stops.
- StaticTokenCap:     per-run token cap enforced by an external watchdog that
                      hard-kills the run.
- Layered:            reservations against hierarchical budgets, health-gated
                      cap extensions, run and tenant velocity, novelty-based
                      loop detection, tool and run circuit breakers, and
                      graceful (compensating) stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .breaker import CircuitBreaker
from .ledger import BudgetExceeded, Ledger
from .pricing import to_micros, to_usd
from .sim import Controller, Decision, Run, Step
from .stop import StopMode
from .velocity import NoveltyTracker, SpendWindow


class NoGuard(Controller):
    name = "none"


class MonthlyBudgetAlert(Controller):
    name = "monthly_alert"

    def __init__(self, budget_usd: float = 200.0, threshold: float = 0.8, reporting_delay_s: float = 1800.0) -> None:
        self.budget = to_micros(budget_usd)
        self.threshold = threshold
        self.delay = reporting_delay_s
        self.spent = 0
        self.crossed_at: Optional[float] = None

    def after_model(self, run, step, cost, decision, now):
        self.spent += cost
        if self.crossed_at is None and self.spent >= self.threshold * self.budget:
            self.crossed_at = now

    def alerts(self):
        if self.crossed_at is None:
            return []
        t = self.crossed_at + self.delay
        return [(t, f"{int(self.threshold * 100)}% of monthly budget (seen at t={t / 60:.1f} min)")]


class StaticTokenCap(Controller):
    name = "static_token_cap"

    def __init__(self, max_tokens_per_run: int = 2_000_000) -> None:
        self.cap = max_tokens_per_run

    def _check(self, run: Run) -> Decision:
        if run.tokens > self.cap:
            return Decision.stop(f"token cap {self.cap:,} exceeded (watchdog kill)", StopMode.HARD)
        return Decision.proceed()

    def before_step(self, run, step, now):
        return self._check(run)

    def before_commit(self, run, now):
        return self._check(run)


@dataclass
class LayeredConfig:
    tenant_budget_usd: float = 200.0
    run_budget_usd: float = 5.0  # initial per-run budget; covers the run's descendants
    max_extensions: int = 5  # each extension doubles the run budget
    max_tree_runs: int = 16  # a subtree larger than this is never auto-extended
    max_output_tokens: int = 4096  # worst case used for reservations
    run_rate_usd_per_min: float = 2.0
    run_rate_window_s: float = 60.0
    run_throttle_s: float = 10.0
    tenant_rate_usd_per_min: float = 5.0
    tenant_rate_window_s: float = 120.0
    tenant_throttle_s: float = 20.0
    novelty_window: int = 20
    novelty_min_samples: int = 10
    novelty_floor: float = 0.4
    tool_failure_threshold: int = 5
    tool_failure_window_s: float = 60.0
    tool_cooldown_s: float = 120.0
    max_tool_rejections: int = 3
    hierarchical: bool = True  # child budgets draw from the parent's; False = every run is capped on its own
    # --- v2 additions (all off by default, so v1 behaviour is unchanged) ---
    long_novelty_window: int = 0  # second, longer novelty window to expose long cycles (0 = off)
    long_novelty_floor: float = 0.4
    max_tree_depth: Optional[int] = None  # if set, extension health checks subtree *depth*, not size
    max_run_budget_usd: Optional[float] = None  # hard ceiling: extensions never go past this
    novelty_exempt_prefixes: tuple = ()  # actions declared as waits (e.g. "poll:") don't count toward novelty
    run_token_cap: Optional[int] = None  # static per-run token cap, enforced with a graceful stop (None = off)


def layered_combined_config(**overrides) -> LayeredConfig:
    """Combined baseline: v2 plus the static 2M-token per-run cap, stopped
    gracefully instead of hard-killed. Answers: does keeping the simple cap
    alongside the layered design help, hurt, or change nothing?"""
    return layered_v2_config(run_token_cap=2_000_000, **overrides)


def ceiling_only_config(ceiling_usd: float = 100.0, **overrides) -> LayeredConfig:
    """Simplest sensible baseline: a hierarchical dollar ceiling per run tree and
    nothing else. Reservations and hierarchy stay on; extensions, novelty, run
    breakers, circuit breakers and throttling are all off. Answers: what do the
    detectors buy over a plain tree-wide dollar limit?"""
    from dataclasses import replace
    base = LayeredConfig(
        run_budget_usd=ceiling_usd,
        max_extensions=0,
        novelty_floor=0.0,  # ratio is never < 0, so loop detection never fires
        max_tool_rejections=10**9,
        tool_failure_threshold=10**9,  # breakers never open
        run_rate_usd_per_min=1e9,
        tenant_rate_usd_per_min=1e9,  # no throttling
    )
    return replace(base, **overrides)


def layered_v3_config(**overrides) -> LayeredConfig:
    """Proposed configuration: v2 with tree depth 8, the one change the v2
    sensitivity sweep (seeds 1000-1029) pointed to. Evaluated on seeds
    2000-2029, which no version was designed against."""
    return layered_v2_config(max_tree_depth=8, **overrides)


def layered_v2_config(**overrides) -> LayeredConfig:
    """Fixes for v1 failures found by the randomized suite (see README).

    - Two novelty windows (20 and 100 steps): long planning cycles hide inside a
      short window but not a long one.
    - Extension health checks depth, not size: recursion grows deep, legitimate
      fan-out grows wide. The size limit stays as a loose backstop.
    - Absolute per-run ceiling, so a run that fools every signal is still bounded.
    - Declared wait actions are exempt from novelty, so polling isn't a "loop".
    """
    base = LayeredConfig(
        long_novelty_window=100,
        long_novelty_floor=0.4,
        max_tree_depth=3,
        max_tree_runs=256,
        max_run_budget_usd=100.0,  # no run tree spends > half the tenant budget without a human
        novelty_exempt_prefixes=("poll:",),
    )
    from dataclasses import replace
    return replace(base, **overrides)


class Layered(Controller):
    name = "layered"

    def __init__(self, cfg: Optional[LayeredConfig] = None, name: Optional[str] = None) -> None:
        self.cfg = cfg or LayeredConfig()
        if name:
            self.name = name
        self.ledger = Ledger()
        self.owner: dict[str, Run] = {}
        self.run_window: dict[str, SpendWindow] = {}
        self.novelty: dict[str, NoveltyTracker] = {}
        self.long_novelty: dict[str, NoveltyTracker] = {}
        self.tenant_window: dict[str, SpendWindow] = {}
        self.breakers: dict[tuple[str, str], CircuitBreaker] = {}
        self._res_seq = 0

    # -- bookkeeping -----------------------------------------------------
    @staticmethod
    def _key(run: Run) -> str:
        return f"run:{run.id}"

    def open_run(self, run, now):
        c = self.cfg
        tkey = f"tenant:{run.tenant}"
        if tkey not in self.ledger:
            self.ledger.open(tkey, to_micros(c.tenant_budget_usd))
            self.tenant_window[run.tenant] = SpendWindow(c.tenant_rate_window_s)
        parent = self._key(run.parent) if (run.parent and c.hierarchical) else tkey
        key = self._key(run)
        self.ledger.open(key, to_micros(c.run_budget_usd), parent)
        self.owner[key] = run
        self.run_window[run.id] = SpendWindow(c.run_rate_window_s)
        self.novelty[run.id] = NoveltyTracker(c.novelty_window, c.novelty_min_samples)
        if c.long_novelty_window:
            self.long_novelty[run.id] = NoveltyTracker(c.long_novelty_window, c.long_novelty_window // 2)

    def _breaker(self, tenant: str, tool: str) -> CircuitBreaker:
        k = (tenant, tool)
        if k not in self.breakers:
            c = self.cfg
            self.breakers[k] = CircuitBreaker(c.tool_failure_threshold, c.tool_failure_window_s, c.tool_cooldown_s)
        return self.breakers[k]

    # -- signals ---------------------------------------------------------
    def _looping(self, run: Run) -> Optional[float]:
        r = self.novelty[run.id].ratio()
        if r is not None and r < self.cfg.novelty_floor:
            return r
        lt = self.long_novelty.get(run.id)
        if lt is not None:
            r = lt.ratio()
            if r is not None and r < self.cfg.long_novelty_floor:
                return r
        return None

    def _run_rate_usd(self, run: Run, now: float) -> float:
        return to_usd(self.run_window[run.id].rate_per_min(now))

    def _healthy(self, run: Run, now: float) -> bool:
        return (
            self._looping(run) is None
            and run.tool_rejections == 0
            and self._run_rate_usd(run, now) <= self.cfg.run_rate_usd_per_min
        )

    def _can_extend(self, owner: Run, now: float) -> bool:
        if owner.extensions >= self.cfg.max_extensions:
            return False
        c = self.cfg
        tree = list(owner.subtree())
        if len(tree) > c.max_tree_runs:
            return False
        if c.max_tree_depth is not None and max(r.depth for r in tree) - owner.depth > c.max_tree_depth:
            return False
        if c.max_run_budget_usd is not None:
            limit = self.ledger.budgets[self._key(owner)].limit
            if limit is not None and limit >= to_micros(c.max_run_budget_usd):
                return False
        return all(self._healthy(r, now) for r in tree if r.status == "active")

    def _stop_tree(self, run: Run, reason: str, now: float) -> Decision:
        for r in run.subtree():
            r.stop.request(reason, StopMode.GRACEFUL, now)
        return Decision.stop(reason, StopMode.GRACEFUL)

    # -- hooks -----------------------------------------------------------
    def before_step(self, run, step, now):
        c = self.cfg
        req = run.stop.requested
        if req is not None:
            return Decision.stop(req.reason, req.mode)

        if c.run_token_cap is not None and run.tokens > c.run_token_cap:
            return self._stop_tree(run, f"token cap {c.run_token_cap:,} exceeded (graceful)", now)

        if run.tool_rejections >= c.max_tool_rejections:
            return self._stop_tree(run, "run breaker: agent kept calling a tool whose circuit is open", now)

        nov = self._looping(run)
        if nov is not None:
            return self._stop_tree(run, f"loop detected: action novelty {nov:.2f} < {c.novelty_floor}", now)

        if to_usd(self.tenant_window[run.tenant].rate_per_min(now)) > c.tenant_rate_usd_per_min:
            return Decision.throttle(c.tenant_throttle_s, "tenant velocity")
        if self._run_rate_usd(run, now) > c.run_rate_usd_per_min:
            return Decision.throttle(c.run_throttle_s, "run velocity")

        estimate = self.sim.price.cost_micros(step.input_tokens, max(step.output_tokens, c.max_output_tokens))
        for _ in range(c.max_extensions + 2):
            self._res_seq += 1
            try:
                res = self.ledger.reserve(self._key(run), estimate, f"res{self._res_seq}")
                return Decision.proceed(res)
            except BudgetExceeded as e:
                owner = self.owner.get(e.key)
                if owner is not None and self._can_extend(owner, now):
                    limit = self.ledger.budgets[e.key].limit
                    new = limit * 2
                    if c.max_run_budget_usd is not None:
                        new = min(new, to_micros(c.max_run_budget_usd))
                    self.ledger.extend(e.key, new - limit)  # double, up to the ceiling
                    owner.extensions += 1
                    continue
                if owner is None:
                    return self._stop_tree(run.root, f"tenant budget exhausted ({e.key})", now)
                return self._stop_tree(owner, f"budget exhausted for {owner.id} subtree, extension denied", now)
        return self._stop_tree(run, "reservation retries exhausted", now)

    def after_model(self, run, step, cost, decision, now):
        if decision.reservation is not None:
            self.ledger.settle(decision.reservation.id, cost)
        self.run_window[run.id].add(now, cost)
        self.tenant_window[run.tenant].add(now, cost)
        if not step.action.startswith(self.cfg.novelty_exempt_prefixes or ("\0",)):
            self.novelty[run.id].add(step.action)
            if run.id in self.long_novelty:
                self.long_novelty[run.id].add(step.action)

    def tool_allowed(self, run, step, now):
        return self._breaker(run.tenant, step.tool).allow(now)

    def on_tool_result(self, run, step, outcome, now):
        b = self._breaker(run.tenant, step.tool)
        if outcome == "ok":
            b.record_success(now)
        elif outcome == "fail":
            b.record_failure(now)

    def before_commit(self, run, now):
        req = run.stop.requested
        if req is not None:
            return Decision.stop(req.reason, StopMode.GRACEFUL)
        return Decision.proceed()
