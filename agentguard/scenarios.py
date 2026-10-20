"""Scripted workloads: three legitimate, three runaway.

Every step carries a ground-truth `runaway` label so the benchmark can measure
how much money went to the runaway part and when it stopped. Guardrails never
see that label.

Context growth matters: in a loop, each iteration appends tool output to the
context, so every turn of the loop costs more than the last.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from .sim import Step

CONTEXT_LIMIT = 120_000


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    legit: bool
    root: Callable[[], Iterator[Step]]
    tenant: str = "acme"


def _grow(ctx: int, by: int) -> int:
    return min(ctx + by, CONTEXT_LIMIT)


# --- legitimate ---------------------------------------------------------

def normal_task() -> Iterator[Step]:
    ctx = 4_000
    for i in range(12):
        if i % 2 == 0:
            yield Step(f"write_note:{i}", ctx, 400, tool="notes", side_effect=True)
        else:
            yield Step(f"search:{i}", ctx, 400, tool="search")
        ctx = _grow(ctx, 1_500)


def long_task() -> Iterator[Step]:
    """300 files, rolling summary keeps context flat. Expensive in total, but making progress."""
    for i in range(300):
        yield Step(f"process:file_{i}", 20_000, 400, tool="write_file", side_effect=True)


def _batch_worker(w: int) -> Callable[[], Iterator[Step]]:
    def script() -> Iterator[Step]:
        for i in range(15):
            yield Step(f"summarize:doc_{w}_{i}", 100_000, 2_000, tool="write_summary", side_effect=True)
    return script


def parallel_batch() -> Iterator[Step]:
    """Planner fans out to 8 workers on large documents: fast spend, bounded, all progress."""
    yield Step("plan:batch", 6_000, 800)
    yield Step("dispatch:workers", 8_000, 300, spawn=tuple(_batch_worker(w) for w in range(8)))
    yield Step("report:batch", 10_000, 600)


# --- runaway ------------------------------------------------------------

def tool_retry_loop() -> Iterator[Step]:
    """Normal work, then a downstream API starts failing and the agent retries forever."""
    ctx = 4_000
    for i in range(8):
        yield Step(f"prepare:step_{i}", ctx, 400, tool="search")
        ctx = _grow(ctx, 2_000)
    while True:
        yield Step("call:payments_api{order=123}", ctx, 300, tool="payments_api", tool_fails=True, runaway=True)
        ctx = _grow(ctx, 2_000)


def _recursive_child() -> Iterator[Step]:
    yield Step("plan:subtask", 8_000, 300, runaway=True)
    yield Step("delegate:subtask", 8_000, 300, spawn=(_recursive_child, _recursive_child), runaway=True)
    for i in range(3):
        yield Step(f"work:subtask_{i}", 8_000, 300, tool="write_result", side_effect=True, runaway=True)


def recursive_spawn() -> Iterator[Step]:
    """A delegation bug: every sub-agent decides the task needs two more sub-agents."""
    ctx = 4_000
    for i in range(3):
        yield Step(f"analyze:{i}", ctx, 400)
        ctx = _grow(ctx, 1_500)
    yield Step("delegate:task", ctx, 300, spawn=(_recursive_child, _recursive_child), runaway=True)
    for i in range(5):
        yield Step(f"await:{i}", ctx, 200, runaway=True)


def nonconverging_plan() -> Iterator[Step]:
    """Planner cycles through three plans, drafting each, never converging.

    Each call is different from the previous one, so an "identical call
    repeated N times" check never fires.
    """
    ctx = 4_000
    for i in range(5):
        yield Step(f"research:{i}", ctx, 400, tool="search")
        ctx = _grow(ctx, 1_500)
    plans = ["A", "B", "C"]
    i = 0
    while True:
        p = plans[i % 3]
        yield Step(f"plan:{p}", ctx, 500, runaway=True)
        ctx = _grow(ctx, 2_500)
        yield Step(f"draft:{p}", ctx, 600, tool="write_draft", side_effect=True, runaway=True)
        ctx = _grow(ctx, 2_500)
        i += 1


SCENARIOS = [
    Scenario("normal_task", "12-step task with notes and searches", True, normal_task),
    Scenario("long_task", "300-step task over many files (legit, expensive)", True, long_task),
    Scenario("parallel_batch", "fan-out to 8 workers on large docs (legit, fast spend)", True, parallel_batch),
    Scenario("tool_retry_loop", "retries a failing API forever", False, tool_retry_loop),
    Scenario("recursive_spawn", "every sub-agent spawns two more", False, recursive_spawn),
    Scenario("nonconverging_plan", "cycles between 3 plans, never finishes", False, nonconverging_plan),
]
