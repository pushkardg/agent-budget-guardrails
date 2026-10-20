"""Combined baseline: v2 plus a static per-run token cap (graceful stop), at several cap levels.

    python -m agentguard.capsweep --out results

Question it answers: if you keep the simple token cap alongside the layered
design, is there a cap level that stops runaways sooner without killing
legitimate long work?
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics

from .controllers import Layered, layered_v2_config
from .pricing import to_usd
from .robustness import contained, run_family, wilson
from .variants import FAMILIES

CAPS = [None, 2_000_000, 4_000_000, 8_000_000, 16_000_000]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results")
    ap.add_argument("--seed-start", type=int, default=2000)
    ap.add_argument("--seeds", type=int, default=30)
    args = ap.parse_args()
    seeds = range(args.seed_start, args.seed_start + args.seeds)

    legit = [f for f in FAMILIES if f.legit]
    runaway = [f for f in FAMILIES if not f.legit]
    lines = [
        f"# v2 plus a static per-run token cap (graceful stop), seeds {seeds.start}-{seeds.stop - 1}",
        "",
        "Legitimate work: % completed. Runaways: % contained (median runaway spend).",
        "",
        "| Family | " + " | ".join("v2 alone" if c is None else f"cap {c // 1_000_000}M" for c in CAPS) + " |",
        "|" + "---|" * (len(CAPS) + 1),
    ]
    results = {}
    for cap in CAPS:
        def make(cap=cap):
            return Layered(layered_v2_config(run_token_cap=cap))
        for fam in FAMILIES:
            results[(fam.name, cap)] = run_family(fam, make, seeds)
    rows = []
    for fam in legit + runaway:
        cells = []
        for cap in CAPS:
            rs = results[(fam.name, cap)]
            if fam.legit:
                k = sum(r.work_completed for r in rs)
                cells.append(f"{round(100 * k / len(rs))}%")
                rows.append({"family": fam.name, "cap": cap or 0, "completed_pct": round(100 * k / len(rs)),
                             "orphaned_writes": sum(r.orphaned for r in rs)})
            else:
                k = sum(contained(r) for r in rs)
                med = statistics.median(to_usd(r.runaway_cost) for r in rs)
                cells.append(f"{round(100 * k / len(rs))}% (${med:.2f})")
                rows.append({"family": fam.name, "cap": cap or 0, "contained_pct": round(100 * k / len(rs)),
                             "median_runaway_usd": round(med, 2)})
        lines.append(f"| {fam.name} | " + " | ".join(cells) + " |")
    lo, hi = wilson(30, 30)
    lines += ["", f"30 runs per cell; 30/30 has a 95% interval of {lo}-{hi}%."]
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "cap_sweep.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["family", "cap", "completed_pct", "orphaned_writes",
                                          "contained_pct", "median_runaway_usd"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "cap_sweep.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
