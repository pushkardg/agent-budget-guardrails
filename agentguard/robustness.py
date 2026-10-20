"""Robustness suite and threshold sensitivity sweep over randomized scenario families.

    python -m agentguard.robustness --out results --seeds 30
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
from dataclasses import replace
from typing import Callable

import math

from .controllers import (Layered, LayeredConfig, MonthlyBudgetAlert, NoGuard, StaticTokenCap,
                          layered_combined_config, layered_v2_config, layered_v3_config)
from .pricing import to_usd
from .sim import Controller, SimResult, Simulator
from .variants import FAMILIES, Family

HORIZON_S = 3600.0
MAX_RUNS = 2000

CONTROLLERS: dict[str, Callable[[], Controller]] = {
    "none": NoGuard,
    "monthly_alert": MonthlyBudgetAlert,
    "static_token_cap": StaticTokenCap,
    "layered_v1": lambda: Layered(name="layered_v1"),
    "layered_v2": lambda: Layered(layered_v2_config(), name="layered_v2"),
    "layered_v3": lambda: Layered(layered_v3_config(), name="layered_v3"),
    "v2_plus_cap": lambda: Layered(layered_combined_config(), name="v2_plus_cap"),
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n, as percentages."""
    if n == 0:
        return (0.0, 100.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1))


def _ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{lo}-{hi}"


def contained(r: SimResult) -> bool:
    return not r.hit_horizon and r.spawn_capped == 0


def run_family(fam: Family, make: Callable[[], Controller], seeds: range) -> list[SimResult]:
    return [Simulator(fam.make(s), make(), horizon_s=HORIZON_S, max_runs=MAX_RUNS).run() for s in seeds]


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))
    return xs[k]


def summarize(fam: Family, ctl: str, rs: list[SimResult], baseline: list[SimResult] | None) -> dict:
    row = {"family": fam.name, "type": "legit" if fam.legit else "runaway",
           "adversarial": fam.adversarial, "guardrail": ctl, "n": len(rs)}
    if fam.legit:
        k = sum(r.work_completed for r in rs)
        row["completed_pct"] = round(100 * k / len(rs))
        row["completed_ci95"] = _ci(k, len(rs))
        row["orphaned_writes"] = sum(r.orphaned for r in rs)
        if baseline:
            slow = [100 * (r.ended_at / b.ended_at - 1) for r, b in zip(rs, baseline) if r.work_completed and b.ended_at > 0]
            row["median_slowdown_pct"] = round(statistics.median(slow), 1) if slow else ""
    else:
        caught = [r for r in rs if contained(r)]
        row["contained_pct"] = round(100 * len(caught) / len(rs))
        row["contained_ci95"] = _ci(len(caught), len(rs))
        spend = [to_usd(r.runaway_cost) for r in rs]
        row["median_runaway_usd"] = round(statistics.median(spend), 2)
        row["p95_runaway_usd"] = round(_pct(spend, 0.95), 2)
        ttc = [r.time_to_contain_s for r in caught if r.time_to_contain_s is not None]
        row["median_contain_s"] = round(statistics.median(ttc)) if ttc else ""
        row["orphaned_writes"] = sum(r.orphaned for r in rs)
    return row


def robustness(seeds: range) -> list[dict]:
    rows = []
    for fam in FAMILIES:
        base = run_family(fam, NoGuard, seeds)
        for name, make in CONTROLLERS.items():
            rs = base if name == "none" else run_family(fam, make, seeds)
            rows.append(summarize(fam, name, rs, base))
    return rows


# --- sensitivity ----------------------------------------------------------

B = layered_v2_config()
SWEEP: list[tuple[str, str, LayeredConfig]] = (
    [("novelty_floor", str(v), replace(B, novelty_floor=v)) for v in (0.2, 0.3, 0.4, 0.5, 0.6)]
    + [("long_novelty_window", str(v), replace(B, long_novelty_window=v)) for v in (0, 50, 100, 200)]
    + [("max_tree_depth", str(v), replace(B, max_tree_depth=v)) for v in (2, 3, 5, 8)]
    + [("run_budget_usd", str(v), replace(B, run_budget_usd=v)) for v in (1.0, 5.0, 20.0)]
    + [("max_run_budget_usd", str(v), replace(B, max_run_budget_usd=v)) for v in (25.0, 50.0, 100.0, 200.0)]
    + [("max_tool_rejections", str(v), replace(B, max_tool_rejections=v)) for v in (1, 3, 10)]
)


def sensitivity(seeds: range) -> list[dict]:
    rows = []
    for param, value, cfg in SWEEP:
        legit_ok = legit_n = run_ok = run_n = 0
        spend = []
        failures = []
        for fam in FAMILIES:
            rs = run_family(fam, lambda: Layered(cfg), seeds)
            if fam.legit:
                ok = sum(r.work_completed for r in rs)
                legit_ok += ok
                legit_n += len(rs)
                if ok < len(rs):
                    failures.append(f"{fam.name} killed {len(rs) - ok}/{len(rs)}")
            else:
                ok = sum(contained(r) for r in rs)
                run_ok += ok
                run_n += len(rs)
                spend += [to_usd(r.runaway_cost) for r in rs]
                if ok < len(rs):
                    failures.append(f"{fam.name} missed {len(rs) - ok}/{len(rs)}")
        rows.append({
            "parameter": param,
            "value": value,
            "default": value == _default(param),
            "legit_completed_pct": round(100 * legit_ok / legit_n, 1),
            "runaway_contained_pct": round(100 * run_ok / run_n, 1),
            "mean_runaway_usd": round(statistics.mean(spend), 2),
            "failures": "; ".join(failures),
        })
    return rows


def _default(param: str) -> str:
    return str(getattr(B, param))


# --- output ---------------------------------------------------------------

def _md(rows: list[dict], cols: list[str], head: list[str]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


def _csv(path: str, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--seed-start", type=int, default=2000,
                    help="seed history: v1 -> v2 designed looking at 0-29; v2 -> v3 at 1000-1029; "
                         "default 2000-2029 was used by no design decision")
    ap.add_argument("--sens-seed-start", type=int, default=1000,
                    help="sensitivity sweep seeds (default 1000-1029: the sweep that led to v3)")
    args = ap.parse_args()
    seeds = range(args.seed_start, args.seed_start + args.seeds)
    sens_seeds = range(args.sens_seed_start, args.sens_seed_start + args.seeds)
    os.makedirs(args.out, exist_ok=True)

    rob = robustness(seeds)
    _csv(os.path.join(args.out, "robustness.csv"), rob)
    legit = [r for r in rob if r["type"] == "legit"]
    runaway = [r for r in rob if r["type"] == "runaway"]
    md = (
        f"# Robustness: {args.seeds} randomized seeds per family (seeds {seeds.start}-{seeds.stop - 1}), "
        f"{HORIZON_S / 60:.0f}-minute horizon\n\n"
        "Families marked * were written to defeat layered_v1; ** were written afterwards to defeat layered_v2.\n"
        "95% CI = Wilson score interval on n runs: 30/30 means the true rate is very likely above ~89%, not that it is 100%.\n\n"
        "## Legitimate workloads\n\n"
        + _md([{**r, "family": r["family"] + {"": "", "v1": "*", "v2": "**"}[r["adversarial"]]} for r in legit],
              ["family", "guardrail", "completed_pct", "completed_ci95", "orphaned_writes", "median_slowdown_pct"],
              ["Family", "Guardrail", "Completed %", "95% CI", "Orphaned writes", "Median slowdown vs none %"])
        + "\n\n## Runaway workloads\n\n"
        + _md([{**r, "family": r["family"] + {"": "", "v1": "*", "v2": "**"}[r["adversarial"]]} for r in runaway],
              ["family", "guardrail", "contained_pct", "contained_ci95", "median_runaway_usd", "p95_runaway_usd", "median_contain_s", "orphaned_writes"],
              ["Family", "Guardrail", "Contained %", "95% CI", "Median runaway $", "p95 runaway $", "Median time to contain (s)", "Orphaned writes"])
        + "\n"
    )
    with open(os.path.join(args.out, "robustness.md"), "w") as f:
        f.write(md)
    print(md)

    sens = sensitivity(sens_seeds)
    _csv(os.path.join(args.out, "sensitivity.csv"), sens)
    smd = (
        f"# Sensitivity: layered_v2, one threshold varied at a time "
        f"(seeds {sens_seeds.start}-{sens_seeds.stop - 1} x {len(FAMILIES)} families)\n\n"
        + _md([{**r, "value": r["value"] + (" (default)" if r["default"] else "")} for r in sens],
              ["parameter", "value", "legit_completed_pct", "runaway_contained_pct", "mean_runaway_usd", "failures"],
              ["Parameter", "Value", "Legit completed %", "Runaway contained %", "Mean runaway $", "Where it fails"])
        + "\n"
    )
    with open(os.path.join(args.out, "sensitivity.md"), "w") as f:
        f.write(smd)
    print(smd)


if __name__ == "__main__":
    main()
