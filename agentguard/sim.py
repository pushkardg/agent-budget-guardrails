"""Discrete-event simulator for scripted agents.

No real model is called. Each agent runs a scripted sequence of steps; each
step is one model call (with known input/output tokens) optionally followed by
one tool call. Scripts can loop forever or spawn child agents, which is how the
runaway scenarios are expressed.

Timing model
------------
A step occupies the agent for model latency (+ tool latency). Side-effecting
tools are two-phase: the side effect is *staged* when the tool starts and
*committed* in a separate event when the tool finishes. A stop that lands in
between is the interesting case: a graceful stop compensates the staged op, a
hard kill leaves it orphaned.

A controller (the guardrail strategy under test) is consulted before every
step and before every commit.
"""

from __future__ import annotations

import heapq
import itertools
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from .pricing import Price, model_latency_s
from .stop import StopMode, StopToken

ScriptFactory = Callable[[], Iterator["Step"]]


@dataclass(frozen=True)
class Step:
    action: str  # fingerprint of what the agent is doing, e.g. "call:payments_api{order=123}"
    input_tokens: int
    output_tokens: int
    tool: Optional[str] = None
    side_effect: bool = False
    tool_fails: bool = False
    tool_latency_s: float = 1.0
    spawn: tuple = ()  # tuple of ScriptFactory for child agents
    runaway: bool = False  # ground-truth label: is this step part of a runaway?


@dataclass
class Run:
    id: str
    tenant: str
    parent: Optional["Run"]
    depth: int
    script: Iterator[Step]
    started_at: float
    status: str = "active"  # active | completed | stopped
    stop: StopToken = field(default_factory=StopToken)
    pending: Optional[Step] = None
    inflight: Optional[tuple] = None  # (op_id, step, cost)
    children: list = field(default_factory=list)
    steps_done: int = 0
    checkpoint: int = 0  # last step index whose effects are durable
    cost: int = 0
    tokens: int = 0
    aborted_cost: int = 0
    extensions: int = 0
    throttled_s: float = 0.0
    tool_rejections: int = 0
    end_reason: Optional[str] = None
    ended_at: Optional[float] = None

    @property
    def root(self) -> "Run":
        r = self
        while r.parent is not None:
            r = r.parent
        return r

    def subtree(self) -> Iterator["Run"]:
        stack = [self]
        while stack:
            r = stack.pop()
            yield r
            stack.extend(r.children)


@dataclass
class Decision:
    kind: str  # proceed | throttle | stop
    delay: float = 0.0
    reason: str = ""
    mode: StopMode = StopMode.GRACEFUL
    reservation: object = None

    @staticmethod
    def proceed(reservation: object = None) -> "Decision":
        return Decision("proceed", reservation=reservation)

    @staticmethod
    def throttle(delay: float, reason: str = "") -> "Decision":
        return Decision("throttle", delay=delay, reason=reason)

    @staticmethod
    def stop(reason: str, mode: StopMode = StopMode.GRACEFUL) -> "Decision":
        return Decision("stop", reason=reason, mode=mode)


class Controller:
    """Guardrail strategy. Default: allow everything."""

    name = "base"

    def attach(self, sim: "Simulator") -> None:
        self.sim = sim

    def open_run(self, run: Run, now: float) -> None: ...

    def before_step(self, run: Run, step: Step, now: float) -> Decision:
        return Decision.proceed()

    def after_model(self, run: Run, step: Step, cost: int, decision: Decision, now: float) -> None: ...

    def tool_allowed(self, run: Run, step: Step, now: float) -> bool:
        return True

    def on_tool_result(self, run: Run, step: Step, outcome: str, now: float) -> None: ...

    def before_commit(self, run: Run, now: float) -> Decision:
        return Decision.proceed()

    def close_run(self, run: Run, now: float) -> None: ...

    def finish(self, now: float) -> None: ...

    def alerts(self) -> list[tuple[float, str]]:
        return []


class ExternalSystem:
    """Stands in for the world the agent's tools write to."""

    def __init__(self) -> None:
        self._ids = itertools.count()
        self.staged: dict[str, tuple[str, str]] = {}
        self.committed: list[tuple[str, str]] = []
        self.compensated: list[tuple[str, str]] = []

    def prepare(self, run_id: str, action: str) -> str:
        op = f"op{next(self._ids)}"
        self.staged[op] = (run_id, action)
        return op

    def commit(self, op: str) -> None:
        self.committed.append(self.staged.pop(op))

    def compensate(self, op: str) -> None:
        self.compensated.append(self.staged.pop(op))

    def orphaned(self) -> list[tuple[str, str]]:
        return list(self.staged.values())


@dataclass
class SimResult:
    scenario: str
    controller: str
    legit: bool
    total_cost: int
    runaway_cost: int
    onset_at: Optional[float]
    last_runaway_at: Optional[float]
    ended_at: float
    hit_horizon: bool
    runs: int
    spawn_capped: int
    completed_runs: int
    stopped_runs: int
    stop_reasons: Counter
    steps_done: int
    orphaned: int
    compensated: int
    aborted_cost: int
    stopped_cost: int  # spend by runs that a guardrail stopped
    extensions: int
    throttled_s: float
    alerts: list

    @property
    def work_completed(self) -> bool:
        return self.stopped_runs == 0 and not self.hit_horizon and self.spawn_capped == 0

    @property
    def time_to_contain_s(self) -> Optional[float]:
        if self.onset_at is None or self.hit_horizon or self.spawn_capped:
            return None
        return (self.last_runaway_at or self.onset_at) - self.onset_at


class Simulator:
    def __init__(
        self,
        scenario,
        controller: Controller,
        price: Price | None = None,
        horizon_s: float = 3600.0,
        max_runs: int = 3000,
    ) -> None:
        self.scenario = scenario
        self.controller = controller
        self.price = price or Price()
        self.horizon_s = horizon_s
        self.max_runs = max_runs
        self.now = 0.0
        self.runs: list[Run] = []
        self.external = ExternalSystem()
        self.total_cost = 0
        self.runaway_cost = 0
        self.onset_at: Optional[float] = None
        self.last_runaway_at: Optional[float] = None
        self.spawn_capped = 0
        self.hit_horizon = False
        self._heap: list = []
        self._seq = itertools.count()
        controller.attach(self)

    # -- lifecycle -------------------------------------------------------
    def _spawn(self, parent: Optional[Run], factory: ScriptFactory) -> Run:
        rid = f"run{len(self.runs)}"
        run = Run(
            id=rid,
            tenant=self.scenario.tenant,
            parent=parent,
            depth=0 if parent is None else parent.depth + 1,
            script=factory(),
            started_at=self.now,
        )
        if parent is not None:
            parent.children.append(run)
        self.runs.append(run)
        self.controller.open_run(run, self.now)
        heapq.heappush(self._heap, (self.now, next(self._seq), run))
        return run

    def _finish(self, run: Run, status: str, reason: Optional[str] = None) -> None:
        run.status = status
        run.end_reason = reason
        run.ended_at = self.now
        self.controller.close_run(run, self.now)

    def run(self) -> SimResult:
        self._spawn(None, self.scenario.root)
        while self._heap:
            t, _, run = heapq.heappop(self._heap)
            if t > self.horizon_s:
                self.hit_horizon = True
                self.now = self.horizon_s
                break
            self.now = t
            delay = self._event(run)
            if delay is not None:
                heapq.heappush(self._heap, (t + delay, next(self._seq), run))
        self.controller.finish(self.now)
        return self._result()

    # -- one scheduler event for one run --------------------------------
    def _event(self, run: Run) -> Optional[float]:
        if run.status != "active":
            return None
        ctl = self.controller

        # Phase B: a side-effecting tool call is finishing.
        if run.inflight is not None:
            op, step, cost = run.inflight
            d = ctl.before_commit(run, self.now)
            if d.kind == "stop":
                if d.mode is StopMode.GRACEFUL:
                    self.external.compensate(op)
                    run.aborted_cost += cost
                # HARD: staged op is left behind -> orphaned side effect
                run.inflight = None
                self._finish(run, "stopped", d.reason)
                return None
            self.external.commit(op)
            run.inflight = None
            run.steps_done += 1
            run.checkpoint = run.steps_done
            ctl.on_tool_result(run, step, "ok", self.now)
            return 0.0

        # Phase A: next model call.
        if run.pending is None:
            run.pending = next(run.script, None)
            if run.pending is None:
                self._finish(run, "completed")
                return None
        step = run.pending

        d = ctl.before_step(run, step, self.now)
        if d.kind == "throttle":
            run.throttled_s += d.delay
            return d.delay
        if d.kind == "stop":
            self._finish(run, "stopped", d.reason)
            return None

        cost = self.price.cost_micros(step.input_tokens, step.output_tokens)
        run.cost += cost
        run.tokens += step.input_tokens + step.output_tokens
        self.total_cost += cost
        if step.runaway:
            self.runaway_cost += cost
            if self.onset_at is None:
                self.onset_at = self.now
            self.last_runaway_at = self.now
        ctl.after_model(run, step, cost, d, self.now)
        run.pending = None
        latency = model_latency_s(step.output_tokens)

        for factory in step.spawn:
            if len(self.runs) >= self.max_runs:
                self.spawn_capped += 1
            else:
                self._spawn(run, factory)

        if step.tool is None:
            run.steps_done += 1
            run.checkpoint = run.steps_done
            return latency

        if not ctl.tool_allowed(run, step, self.now):
            run.tool_rejections += 1
            ctl.on_tool_result(run, step, "rejected", self.now)
            run.steps_done += 1
            return latency
        if step.tool_fails:
            ctl.on_tool_result(run, step, "fail", self.now)
            run.steps_done += 1
            return latency + step.tool_latency_s
        if step.side_effect:
            op = self.external.prepare(run.id, step.action)
            run.inflight = (op, step, cost)
            return latency + step.tool_latency_s
        ctl.on_tool_result(run, step, "ok", self.now)
        run.steps_done += 1
        run.checkpoint = run.steps_done
        return latency + step.tool_latency_s

    # -- results ---------------------------------------------------------
    def _result(self) -> SimResult:
        reasons = Counter(r.end_reason for r in self.runs if r.status == "stopped")
        return SimResult(
            scenario=self.scenario.name,
            controller=self.controller.name,
            legit=self.scenario.legit,
            total_cost=self.total_cost,
            runaway_cost=self.runaway_cost,
            onset_at=self.onset_at,
            last_runaway_at=self.last_runaway_at,
            ended_at=self.now,
            hit_horizon=self.hit_horizon,
            runs=len(self.runs),
            spawn_capped=self.spawn_capped,
            completed_runs=sum(r.status == "completed" for r in self.runs),
            stopped_runs=sum(r.status == "stopped" for r in self.runs),
            stop_reasons=reasons,
            steps_done=sum(r.steps_done for r in self.runs),
            # ops still staged by a run that has ended; in-flight ops of runs
            # still active at the horizon are not counted
            orphaned=sum(
                1 for rid, _ in self.external.orphaned()
                if rid not in {r.id for r in self.runs if r.status == "active"}
            ),
            compensated=len(self.external.compensated),
            aborted_cost=sum(r.aborted_cost for r in self.runs),
            stopped_cost=sum(r.cost for r in self.runs if r.status == "stopped"),
            extensions=sum(r.extensions for r in self.runs),
            throttled_s=sum(r.throttled_s for r in self.runs),
            alerts=self.controller.alerts(),
        )
