"""Simplest baseline: a hierarchical dollar ceiling per run tree, no detectors.

    python -m agentguard.ceilingsweep --out results

Question it answers: what do loop detection, breakers and extensions buy over
a plain tree-wide dollar limit? Compared against v2 on the same seeds.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics

from .controllers import Layered, ceiling_only_config, layered_v2_config
from .pricing import to_usd
from .robustness import contained, run_family
from .variants import FAMILIES

CEILINGS = [25.0, 50.0, 100.0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results")
    ap.add_argument("--seed-start", type=int, default=2000)
    ap.add_argument("--seeds", type=int, default=30)
    args = ap.parse_args()
    seeds = range(args.seed_start, args.seed_start + args.seeds)

    strategies = [(f"ceiling_{int(c)}", (lambda c=c: Layered(ceiling_only_config(c)))) for c in CEILINGS]
    strategies.append(("layered_v2", lambda: Layered(layered_v2_config())))
    names = [n for n, _ in strategies]
    lines = [
        f"# Hierarchical dollar ceiling only (no detectors) vs v2, seeds {seeds.start}-{seeds.stop - 1}",
        "",
        "Legitimate: % completed. Runaways: % contained (median runaway spend). "
        "'Contained' needs the guardrail to stop it before the horizon and before the "
        "simulator's 2,000-agent safety cap, so a $100 ceiling on recursion can spend "
        "~$100 and still count as not contained.",
        "",
        "| Family | " + " | ".join(names) + " |",
        "|" + "---|" * (len(names) + 1),
    ]
    rows = []
    for fam in [f for f in FAMILIES if f.legit] + [f for f in FAMILIES if not f.legit]:
        cells = []
        for name, make in strategies:
            rs = run_family(fam, make, seeds)
            if fam.legit:
                k = sum(r.work_completed for r in rs)
                pct = round(100 * k / len(rs))
                cells.append(f"{pct}%")
                rows.append({"family": fam.name, "strategy": name, "completed_pct": pct})
            else:
                k = sum(contained(r) for r in rs)
                med = statistics.median(to_usd(r.runaway_cost) for r in rs)
                pct = round(100 * k / len(rs))
                cells.append(f"{pct}% (${med:.2f})")
                rows.append({"family": fam.name, "strategy": name, "contained_pct": pct,
                             "median_runaway_usd": round(med, 2)})
        lines.append(f"| {fam.name} | " + " | ".join(cells) + " |")
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ceiling_sweep.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["family", "strategy", "completed_pct", "contained_pct", "median_runaway_usd"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "ceiling_sweep.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
