"""Randomized scenario families for robustness testing.

The fixed scenarios in scenarios.py were written alongside the guardrails, so
they can't show whether the design is overfit. These families draw their shape
from a seeded RNG, and several were written specifically to break the layered
design:

- polling:       legitimate but repetitive. Looks like a loop to novelty detection.
- wide_batch:    legitimate fan-out that can exceed the subtree-size limit.
- retry_varying: a retry loop whose arguments change every attempt, so no two
                 calls share a fingerprint.
- long_cycle:    a non-converging planner whose cycle is long enough to hide
                 inside the novelty window.
- slow_drip:     paginates forever with a small, flat context. Cheap per step,
                 never repeats an action.

Written after v2, to break the v2 fixes:

- deep_delegation: legitimate, finite delegation chains 4-6 levels deep. Trips
                   v2's depth-based tree health check.
- stuck_poll:      polls a job that never finishes. Exploits v2's exemption of
                   declared wait actions from novelty.

Each family returns a Scenario for a given seed. Everything stays deterministic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterator

from .scenarios import CONTEXT_LIMIT, Scenario
from .sim import Step


def _j(rng: random.Random, base: int, pct: float = 0.2) -> int:
    """Jitter an integer by +/- pct."""
    return max(1, round(base * rng.uniform(1 - pct, 1 + pct)))


def _grow(ctx: int, by: int) -> int:
    return min(ctx + by, CONTEXT_LIMIT)


@dataclass(frozen=True)
class Family:
    name: str
    legit: bool
    adversarial: str  # "" or which design it was written to defeat: "v1" or "v2"
    make: Callable[[int], Scenario]
    note: str


# --- legitimate -----------------------------------------------------------

def normal_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    n = rng.randint(5, 30)
    growth = rng.randint(800, 2_500)

    def script() -> Iterator[Step]:
        ctx = _j(rng, 4_000)
        for i in range(n):
            tool = rng.choice(["search", "notes", None])
            yield Step(f"task:{i}:{tool}", ctx, _j(rng, 400), tool=tool, side_effect=(tool == "notes"))
            ctx = _grow(ctx, growth)
    return Scenario(f"normal_var#{seed}", "", True, script)


def long_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    n = rng.randint(100, 400)
    ctx = rng.randint(12_000, 28_000)

    def script() -> Iterator[Step]:
        for i in range(n):
            yield Step(f"process:file_{i}", _j(rng, ctx, 0.15), _j(rng, 400), tool="write_file", side_effect=True)
    return Scenario(f"long_var#{seed}", "", True, script)


def _worker(rng: random.Random, w: int, docs: int, ctx: int) -> Callable[[], Iterator[Step]]:
    def script() -> Iterator[Step]:
        for i in range(docs):
            yield Step(f"summarize:doc_{w}_{i}", _j(rng, ctx, 0.25), _j(rng, 1_500), tool="write_summary", side_effect=True)
    return script


def batch_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    workers, docs, ctx = rng.randint(3, 12), rng.randint(5, 20), rng.randint(40_000, 110_000)

    def script() -> Iterator[Step]:
        yield Step("plan:batch", 6_000, 800)
        yield Step("dispatch", 8_000, 300, spawn=tuple(_worker(rng, w, docs, ctx) for w in range(workers)))
        yield Step("report", 10_000, 600)
    return Scenario(f"batch_var#{seed}", "", True, script)


def wide_batch(seed: int) -> Scenario:
    """Adversarial: legitimate fan-out to 17-40 workers, above the default subtree limit of 16."""
    rng = random.Random(seed)
    workers, docs, ctx = rng.randint(17, 40), rng.randint(3, 8), rng.randint(20_000, 60_000)

    def script() -> Iterator[Step]:
        yield Step("plan:batch", 6_000, 800)
        yield Step("dispatch", 8_000, 300, spawn=tuple(_worker(rng, w, docs, ctx) for w in range(workers)))
        yield Step("report", 10_000, 600)
    return Scenario(f"wide_batch#{seed}", "", True, script)


def polling(seed: int) -> Scenario:
    """Adversarial: waits on an external job by polling its status, then finishes the work."""
    rng = random.Random(seed)
    polls = rng.randint(15, 60)

    def script() -> Iterator[Step]:
        yield Step("submit:job", 5_000, 300, tool="jobs_api")
        for _ in range(polls):
            yield Step("poll:job_status", 6_000, 100, tool="jobs_api", tool_latency_s=rng.uniform(20, 40))
        for i in range(5):
            yield Step(f"process:result_{i}", 10_000, 400, tool="write_file", side_effect=True)
    return Scenario(f"polling#{seed}", "", True, script)


def _deep(rng: random.Random, depth_left: int) -> Callable[[], Iterator[Step]]:
    def script() -> Iterator[Step]:
        yield Step(f"plan:level_{depth_left}", _j(rng, 30_000), _j(rng, 800))
        kids = tuple(_deep(rng, depth_left - 1) for _ in range(rng.randint(1, 2))) if depth_left > 0 else ()
        yield Step(f"delegate:level_{depth_left}", _j(rng, 30_000), _j(rng, 400), spawn=kids)
        for i in range(rng.randint(4, 10)):
            yield Step(f"work:level_{depth_left}_{i}", _j(rng, 40_000), _j(rng, 800), tool="write_file", side_effect=True)
    return script


def deep_delegation(seed: int) -> Scenario:
    """Adversarial (v2): legitimate delegation 4-6 levels deep, finite and making progress."""
    rng = random.Random(seed)
    return Scenario(f"deep_delegation#{seed}", "", True, _deep(rng, rng.randint(4, 6)))


# --- runaway --------------------------------------------------------------

def retry_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    onset, growth = rng.randint(3, 15), rng.randint(1_000, 3_000)

    def script() -> Iterator[Step]:
        ctx = _j(rng, 4_000)
        for i in range(onset):
            yield Step(f"prepare:{i}", ctx, _j(rng, 400), tool="search")
            ctx = _grow(ctx, growth)
        while True:
            yield Step("call:payments_api{order=123}", ctx, _j(rng, 300), tool="payments_api", tool_fails=True, runaway=True)
            ctx = _grow(ctx, growth)
    return Scenario(f"retry_var#{seed}", "", False, script)


def retry_varying(seed: int) -> Scenario:
    """Adversarial: each retry changes its arguments, so every fingerprint is unique."""
    rng = random.Random(seed)
    onset, growth = rng.randint(3, 15), rng.randint(1_000, 3_000)

    def script() -> Iterator[Step]:
        ctx = _j(rng, 4_000)
        for i in range(onset):
            yield Step(f"prepare:{i}", ctx, _j(rng, 400), tool="search")
            ctx = _grow(ctx, growth)
        attempt = 0
        while True:
            attempt += 1
            yield Step(f"call:payments_api{{order=123,attempt={attempt}}}", ctx, _j(rng, 300),
                       tool="payments_api", tool_fails=True, runaway=True)
            ctx = _grow(ctx, growth)
    return Scenario(f"retry_varying#{seed}", "", False, script)


def _rchild(rng: random.Random, branching: int, work: int) -> Callable[[], Iterator[Step]]:
    def script() -> Iterator[Step]:
        yield Step("plan:subtask", _j(rng, 8_000), _j(rng, 300), runaway=True)
        yield Step("delegate:subtask", _j(rng, 8_000), _j(rng, 300),
                   spawn=tuple(_rchild(rng, branching, work) for _ in range(branching)), runaway=True)
        for i in range(work):
            yield Step(f"work:subtask_{i}", _j(rng, 8_000), _j(rng, 300), tool="write_result", side_effect=True, runaway=True)
    return script


def recursive_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    branching, work = rng.randint(2, 3), rng.randint(1, 5)

    def script() -> Iterator[Step]:
        for i in range(rng.randint(1, 5)):
            yield Step(f"analyze:{i}", _j(rng, 5_000), 400)
        yield Step("delegate:task", 6_000, 300, spawn=tuple(_rchild(rng, branching, work) for _ in range(branching)), runaway=True)
        for i in range(5):
            yield Step(f"await:{i}", 6_000, 200, runaway=True)
    return Scenario(f"recursive_var#{seed}", "", False, script)


def _cycle(rng: random.Random, seed: int, plans: int, per_plan: int, label: str) -> Scenario:
    growth = rng.randint(1_500, 3_000)

    def script() -> Iterator[Step]:
        ctx = _j(rng, 4_000)
        for i in range(rng.randint(3, 10)):
            yield Step(f"research:{i}", ctx, _j(rng, 400), tool="search")
            ctx = _grow(ctx, growth)
        i = 0
        while True:
            p = i % plans
            for a in range(per_plan):
                tool = "write_draft" if a == per_plan - 1 else None
                yield Step(f"plan:{p}:{a}", ctx, _j(rng, 500), tool=tool, side_effect=tool is not None, runaway=True)
                ctx = _grow(ctx, growth)
            i += 1
    return Scenario(f"{label}#{seed}", "", False, script)


def cycle_var(seed: int) -> Scenario:
    rng = random.Random(seed)
    return _cycle(rng, seed, rng.randint(2, 4), rng.randint(1, 2), "cycle_var")


def long_cycle(seed: int) -> Scenario:
    """Adversarial: cycle of 12-30 distinct actions, longer than the 20-step novelty window can expose."""
    rng = random.Random(seed)
    plans = rng.randint(6, 10)
    return _cycle(rng, seed, plans, rng.randint(2, 3), "long_cycle")


def slow_drip(seed: int) -> Scenario:
    """Adversarial: paginates forever (the API keeps returning a next-page token), small flat context."""
    rng = random.Random(seed)
    ctx = rng.randint(4_000, 8_000)

    def script() -> Iterator[Step]:
        yield Step("start:export", ctx, 300)
        page = 0
        while True:
            page += 1
            yield Step(f"fetch:page_{page}", ctx, _j(rng, 200), tool="export_api",
                       tool_latency_s=rng.uniform(5, 15), runaway=True)
    return Scenario(f"slow_drip#{seed}", "", False, script)


def stuck_poll(seed: int) -> Scenario:
    """Adversarial (v2): polls a job that never completes."""
    rng = random.Random(seed)

    def script() -> Iterator[Step]:
        yield Step("submit:job", 5_000, 300, tool="jobs_api")
        while True:
            yield Step("poll:job_status", 6_000, 100, tool="jobs_api",
                       tool_latency_s=rng.uniform(20, 40), runaway=True)
    return Scenario(f"stuck_poll#{seed}", "", False, script)


FAMILIES = [
    Family("normal_var", True, "", normal_var, "5-30 mixed steps"),
    Family("long_var", True, "", long_var, "100-400 steps, flat context"),
    Family("batch_var", True, "", batch_var, "3-12 workers on large docs"),
    Family("wide_batch", True, "v1", wide_batch, "17-40 workers: exceeds subtree limit"),
    Family("polling", True, "v1", polling, "repeats one status call 15-60 times"),
    Family("retry_var", False, "", retry_var, "identical retries, random onset/growth"),
    Family("retry_varying", False, "v1", retry_varying, "retries with changing args"),
    Family("recursive_var", False, "", recursive_var, "branching 2-3, 1-5 work steps"),
    Family("cycle_var", False, "", cycle_var, "cycles of 2-8 actions"),
    Family("long_cycle", False, "v1", long_cycle, "cycles of 12-30 actions"),
    Family("slow_drip", False, "v1", slow_drip, "endless pagination, cheap steps"),
    Family("deep_delegation", True, "v2", deep_delegation, "legit delegation 4-6 levels deep"),
    Family("stuck_poll", False, "v2", stuck_poll, "polls a job that never finishes"),
]
