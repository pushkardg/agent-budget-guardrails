"""Run every scenario against every guardrail strategy and write a report.

    python -m agentguard.bench --out results
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import Callable

from dataclasses import replace

from .controllers import Layered, LayeredConfig, MonthlyBudgetAlert, NoGuard, StaticTokenCap, layered_combined_config, layered_v2_config, layered_v3_config
from .pricing import to_usd
from .scenarios import SCENARIOS
from .sim import Controller, SimResult, Simulator

CONTROLLERS: list[Callable[[], Controller]] = [
    NoGuard, MonthlyBudgetAlert, StaticTokenCap,
    lambda: Layered(name="layered_v1"),
    lambda: Layered(layered_v2_config(), name="layered_v2"),
    lambda: Layered(layered_v3_config(), name="layered_v3"),
    lambda: Layered(layered_combined_config(), name="v2_plus_cap"),
]


_BASE = LayeredConfig()
ABLATIONS: list[Callable[[], Controller]] = [
    lambda: Layered(_BASE, "layered (all layers)"),
    lambda: Layered(replace(_BASE, hierarchical=False), "- hierarchical budgets"),
    lambda: Layered(replace(_BASE, novelty_floor=0.0), "- loop detection"),
    lambda: Layered(replace(_BASE, tool_failure_threshold=10**9, max_tool_rejections=10**9), "- circuit breakers"),
    lambda: Layered(replace(_BASE, max_extensions=0), "- cap extensions"),
    lambda: Layered(replace(_BASE, run_rate_usd_per_min=1e9, tenant_rate_usd_per_min=1e9), "- velocity throttling"),
]


def run_all(horizon_s: float = 3600.0, max_runs: int = 3000, controllers=None) -> list[SimResult]:
    out = []
    for sc in SCENARIOS:
        for make in controllers or CONTROLLERS:
            out.append(Simulator(sc, make(), horizon_s=horizon_s, max_runs=max_runs).run())
    return out


def _fmt_s(s: float | None) -> str:
    if s is None:
        return "—"
    if s < 120:
        return f"{s:.0f} s"
    return f"{s / 60:.1f} min" if s < 7200 else f"{s / 3600:.0f} h"


def outcome(r: SimResult) -> str:
    if r.legit:
        if r.work_completed:
            return "completed"
        reason = r.stop_reasons.most_common(1)[0][0] if r.stop_reasons else "interrupted"
        return f"KILLED: {reason}"
    if r.hit_horizon:
        return "still running at horizon"
    if r.spawn_capped:
        tail = f"; then stopped: {r.stop_reasons.most_common(1)[0][0]}" if r.stop_reasons else ""
        return f"still spawning when simulator capped it at {r.runs} agents{tail}"
    if r.stop_reasons:
        return f"stopped: {r.stop_reasons.most_common(1)[0][0]}"
    return "ended on its own"


def notes(r: SimResult) -> str:
    bits = []
    if r.extensions:
        bits.append(f"{r.extensions} budget extension(s)")
    if r.throttled_s:
        bits.append(f"throttled {_fmt_s(r.throttled_s)} (summed across agents)")
    for t, msg in r.alerts:
        bits.append(f"alert at {t / 60:.0f} min")
    if r.runs > 1:
        bits.append(f"{r.runs} agents")
    return "; ".join(bits)


def to_rows(results: list[SimResult]) -> list[dict]:
    rows = []
    for r in results:
        rows.append({
            "scenario": r.scenario,
            "type": "legit" if r.legit else "runaway",
            "guardrail": r.controller,
            "outcome": outcome(r),
            "total_spend_usd": round(to_usd(r.total_cost), 2),
            "runaway_spend_usd": round(to_usd(r.runaway_cost), 2),
            "time_to_contain": "" if r.legit else _fmt_s(r.time_to_contain_s),
            "sim_duration": _fmt_s(r.ended_at),
            "orphaned_side_effects": r.orphaned,
            "rolled_back_side_effects": r.compensated,
            "rolled_back_spend_usd": round(to_usd(r.aborted_cost), 2),
            # customer charge under three billing policies (provider cost is always total_spend)
            "bill_all_usd": round(to_usd(r.total_cost), 2),
            "bill_excl_rolled_back_usd": round(to_usd(r.total_cost - r.aborted_cost), 2),
            "bill_absorb_guardrail_stops_usd": round(to_usd(r.total_cost - r.stopped_cost), 2),
            "notes": notes(r),
        })
    return rows


def to_markdown(rows: list[dict]) -> str:
    cols = ["scenario", "guardrail", "outcome", "total_spend_usd", "runaway_spend_usd",
            "time_to_contain", "sim_duration", "orphaned_side_effects", "rolled_back_side_effects", "notes"]
    head = ["Scenario", "Guardrail", "Outcome", "Total $", "Runaway $", "Time to contain", "Wall time",
            "Orphaned writes", "Rolled-back writes", "Notes"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in rows:
        vals = []
        for c in cols:
            v = row[c]
            vals.append(f"{v:,.2f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _billing_md(rows: list[dict]) -> str:
    head = ["Scenario", "Guardrail", "Provider cost $", "Bill everything $",
            "Don't bill rolled-back work $", "Absorb guardrail-stopped runs $"]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append(f"| {r['scenario']} | {r['guardrail']} | {r['total_spend_usd']:,.2f} | {r['bill_all_usd']:,.2f} | "
                   f"{r['bill_excl_rolled_back_usd']:,.2f} | {r['bill_absorb_guardrail_stops_usd']:,.2f} |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results")
    ap.add_argument("--horizon-min", type=float, default=60.0)
    args = ap.parse_args()
    results = run_all(horizon_s=args.horizon_min * 60)
    rows = to_rows(results)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = to_markdown(rows)
    with open(os.path.join(args.out, "results.md"), "w") as f:
        f.write(f"# Benchmark results (horizon {args.horizon_min:.0f} min, simulated)\n\n{md}\n")
    print(md)

    bill = [r for r in rows if r["type"] == "runaway" or r["outcome"].startswith("KILLED")]
    bmd = _billing_md(bill)
    with open(os.path.join(args.out, "billing.md"), "w") as f:
        f.write("# What the customer is charged, under three billing policies\n\n"
                "Provider cost is always the full spend. The policies differ in who absorbs it.\n\n" + bmd + "\n")

    abl = to_rows(run_all(horizon_s=args.horizon_min * 60, controllers=ABLATIONS))
    with open(os.path.join(args.out, "ablation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(abl[0]))
        w.writeheader()
        w.writerows(abl)
    amd = to_markdown(abl)
    with open(os.path.join(args.out, "ablation.md"), "w") as f:
        f.write(f"# Ablation: layered guardrails with one layer removed\n\n{amd}\n")
    print()
    print(amd)


if __name__ == "__main__":
    main()
