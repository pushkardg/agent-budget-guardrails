"""Bookkeeping cost of one reserve + settle on the in-memory ledger.

    python -m agentguard.overhead --out results

This measures the ledger logic only: one process, one lock, no network. A real
gateway adds a round trip to a shared store (for example a database
transaction or a server-side script) for every model call, which will dominate
these numbers. Treat the output as a floor, not a production estimate.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import threading
import time

from .ledger import Ledger


def build(depth: int) -> tuple[Ledger, str]:
    led = Ledger()
    led.open("tenant", 10**15)
    parent = "tenant"
    for d in range(depth):
        key = f"run{d}"
        led.open(key, 10**14, parent)
        parent = key
    return led, parent


def single(depth: int, n: int) -> list[float]:
    led, leaf = build(depth)
    out = []
    for i in range(n):
        t0 = time.perf_counter_ns()
        led.reserve(leaf, 1000, f"r{i}", now=0.0, ttl_s=300)
        led.settle(f"r{i}", 900)
        out.append((time.perf_counter_ns() - t0) / 1000)  # microseconds
    return out


def concurrent(depth: int, threads: int, per_thread: int) -> float:
    led, leaf = build(depth)

    def work(t: int) -> None:
        for i in range(per_thread):
            rid = f"t{t}-{i}"
            led.reserve(leaf, 1000, rid, now=0.0, ttl_s=300)
            led.settle(rid, 900)

    ts = [threading.Thread(target=work, args=(t,)) for t in range(threads)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return threads * per_thread / (time.perf_counter() - t0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    lines = [
        "# Ledger bookkeeping overhead (in-memory, single process)",
        "",
        f"Python {platform.python_version()} on {platform.machine()}. Ledger logic only; no network or shared store.",
        "",
        "| Budget chain depth | Median reserve+settle (µs) | p99 (µs) | Throughput, 8 threads (ops/s) |",
        "|---|---|---|---|",
    ]
    for depth in (1, 3, 6):
        xs = single(depth, 20_000)
        xs.sort()
        p99 = xs[int(0.99 * len(xs))]
        tput = concurrent(depth, 8, 5_000)
        lines.append(f"| {depth + 1} levels (tenant + {depth} run{'s' if depth > 1 else ''}) | {statistics.median(xs):.1f} | {p99:.1f} | {tput:,.0f} |")
    lines += ["", "A production gateway adds one round trip to a shared store per model call; that, not this logic, sets the real overhead."]
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "overhead.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
