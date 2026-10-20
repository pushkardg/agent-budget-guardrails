"""Check every number the article quotes against the generated result files.

    python -m agentguard.bench --out results
    python -m agentguard.robustness --out results
    python -m agentguard.capsweep --out results
    python -m agentguard.ceilingsweep --out results
    python -m agentguard.verify_claims --results results

Exits non-zero if any claim doesn't match.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys


def load(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pick(rows: list[dict], **match) -> dict:
    hits = [r for r in rows if all(r.get(k) == str(v) for k, v in match.items())]
    if len(hits) != 1:
        raise LookupError(f"expected one row for {match}, found {len(hits)}")
    return hits[0]


def near(actual: float, expected: float, tol: float) -> bool:
    return abs(actual - expected) <= tol


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results")
    args = ap.parse_args()
    R = lambda name: os.path.join(args.results, name)  # noqa: E731

    fixed = load(R("results.csv"))
    abl = load(R("ablation.csv"))
    rob = load(R("robustness.csv"))
    cap = load(R("cap_sweep.csv"))
    ceil = load(R("ceiling_sweep.csv"))
    sens_path = os.path.join(args.results, "seeds_1000", "sensitivity.csv")
    sens = load(sens_path if os.path.exists(sens_path) else R("sensitivity.csv"))

    checks: list[tuple[str, bool, str]] = []

    def claim(text: str, ok: bool, got: object) -> None:
        checks.append((text, ok, str(got)))

    def money(row: dict, col: str) -> float:
        return float(row[col])

    # --- fixed scenarios ---------------------------------------------------
    r = pick(fixed, scenario="tool_retry_loop", guardrail="none")
    claim("Retry loop, no guardrails: about $199 in an hour", near(money(r, "total_spend_usd"), 199, 1), r["total_spend_usd"])
    r = pick(fixed, scenario="recursive_spawn", guardrail="none")
    claim("Recursive spawning, no guardrails: about $428", near(money(r, "total_spend_usd"), 428, 1), r["total_spend_usd"])
    r = pick(fixed, scenario="tool_retry_loop", guardrail="monthly_alert")
    claim("Retry loop alert lands at minute 79", "alert at 79 min" in r["notes"], r["notes"])
    r = pick(fixed, scenario="recursive_spawn", guardrail="monthly_alert")
    m = re.search(r"alert at (\d+) min", r["notes"])
    claim("Recursive alert lands ~29 min after the money was gone (spend ends ~2 min)", m and int(m.group(1)) == 31, r["notes"])
    r = pick(fixed, scenario="tool_retry_loop", guardrail="layered_v1")
    claim("Breaker stops retry loop: 42 s, $0.68", r["time_to_contain"] == "42 s" and near(money(r, "runaway_spend_usd"), 0.68, 0.005), (r["time_to_contain"], r["runaway_spend_usd"]))
    r = pick(fixed, scenario="tool_retry_loop", guardrail="static_token_cap")
    claim("Token cap on retry loop: 3.6 min, $6.10", r["time_to_contain"] == "3.6 min" and near(money(r, "runaway_spend_usd"), 6.10, 0.005), (r["time_to_contain"], r["runaway_spend_usd"]))
    r = pick(fixed, scenario="recursive_spawn", guardrail="layered_v1")
    claim("Hierarchical budgets stop recursion at about $5 in under 30 s", money(r, "runaway_spend_usd") < 5.5 and int(r["time_to_contain"].split()[0]) < 30, (r["runaway_spend_usd"], r["time_to_contain"]))
    claim("Graceful stop rolled back 30 writes, none orphaned", r["rolled_back_side_effects"] == "30" and r["orphaned_side_effects"] == "0", (r["rolled_back_side_effects"], r["orphaned_side_effects"]))
    claim("Billing: $4.94 provider cost, $4.09 excluding rolled-back work", near(money(r, "bill_all_usd"), 4.94, 0.005) and near(money(r, "bill_excl_rolled_back_usd"), 4.09, 0.005), (r["bill_all_usd"], r["bill_excl_rolled_back_usd"]))
    for g in ("layered_v1", "layered_v2"):
        r = pick(fixed, scenario="long_task", guardrail=g)
        claim(f"$20, 300-step task completes under {g}", r["outcome"] == "completed" and near(money(r, "total_spend_usd"), 20, 0.5), (r["outcome"], r["total_spend_usd"]))
        r = pick(fixed, scenario="parallel_batch", guardrail=g)
        claim(f"$40 batch completes under {g}", r["outcome"] == "completed" and near(money(r, "total_spend_usd"), 40, 0.5), (r["outcome"], r["total_spend_usd"]))
    r = pick(fixed, scenario="long_task", guardrail="static_token_cap")
    claim("Fixed scenario: cap kills the 300-step task about a third of the way", r["outcome"].startswith("KILLED"), r["outcome"])

    # --- ablation ----------------------------------------------------------
    r = pick(abl, scenario="recursive_spawn", guardrail="- hierarchical budgets")
    claim("Without hierarchy, recursion spends the whole $200 tenant budget", near(money(r, "total_spend_usd"), 200, 0.5), r["total_spend_usd"])
    for s in ("long_task", "parallel_batch"):
        r = pick(abl, scenario=s, guardrail="- cap extensions")
        claim(f"Without extensions, {s} is killed", r["outcome"].startswith("KILLED"), r["outcome"])
    for s in ("tool_retry_loop", "recursive_spawn", "nonconverging_plan"):
        a = pick(abl, scenario=s, guardrail="- velocity throttling")
        b = pick(abl, scenario=s, guardrail="layered (all layers)")
        claim(f"Removing throttling doesn't make {s} worse", money(a, "runaway_spend_usd") <= money(b, "runaway_spend_usd") + 0.005, (a["runaway_spend_usd"], b["runaway_spend_usd"]))

    # --- randomized results tables (seeds 2000-2029) ------------------------
    legit = {
        "normal_var": [100, 100, 100, 100], "long_var": [0, 100, 100, 100], "batch_var": [97, 100, 100, 100],
        "wide_batch": [100, 0, 100, 100], "polling": [100, 0, 100, 100], "deep_delegation": [100, 50, 0, 100],
    }
    G = ["static_token_cap", "layered_v1", "layered_v2", "layered_v3"]
    for fam, exp in legit.items():
        got = [int(pick(rob, family=fam, guardrail=g)["completed_pct"]) for g in G]
        claim(f"Legit table, {fam}: {exp}", got == exp, got)
    runaway = {
        "retry_var": [(100, 5.99), (100, 0.65), (100, 0.65), (100, 0.65)],
        "retry_varying": [(100, 5.99), (100, 0.65), (100, 0.65), (100, 0.65)],
        "recursive_var": [(0, 342), (100, 4.86), (100, 4.86), (100, 19.85)],
        "cycle_var": [(100, 6.13), (87, 1.97), (100, 1.97), (100, 1.97)],
        "long_cycle": [(100, 6.11), (0, 114), (100, 15.18), (100, 15.18)],
        "slow_drip": [(7, None), (0, None), (0, None), (0, None)],
        "stuck_poll": [(0, None), (100, None), (0, None), (0, None)],
    }
    for fam, exp in runaway.items():
        got = []
        ok = True
        for g, (pct, usd) in zip(G, exp):
            row = pick(rob, family=fam, guardrail=g)
            got.append((int(row["contained_pct"]), row["median_runaway_usd"]))
            ok &= int(row["contained_pct"]) == pct
            if usd is not None:
                ok &= near(float(row["median_runaway_usd"]), usd, 0.5 if usd > 100 else 0.005)
        claim(f"Runaway table, {fam}", ok, got)
    r = pick(rob, family="long_var", guardrail="static_token_cap")
    claim("Cap left 30 half-finished writes across 30 long tasks", r["orphaned_writes"] == "30", r["orphaned_writes"])
    r = pick(rob, family="recursive_var", guardrail="layered_v2")
    r3 = pick(rob, family="recursive_var", guardrail="layered_v3")
    claim("v3 recursion: 152 s instead of 26 s", r["median_contain_s"] == "26" and r3["median_contain_s"] == "152", (r["median_contain_s"], r3["median_contain_s"]))
    for fam, slow in (("wide_batch", 2.0), ("deep_delegation", 1.4)):
        g = "layered_v2" if fam == "wide_batch" else "layered_v3"
        r = pick(rob, family=fam, guardrail=g)
        x = 1 + float(r["median_slowdown_pct"]) / 100
        claim(f"{fam} about {slow}x slower", near(x, slow, 0.1), round(x, 2))
    r = pick(rob, family="slow_drip", guardrail="static_token_cap")
    claim("Static cap caught the slow leak in the last few minutes", float(r["median_contain_s"]) > 3300, r["median_contain_s"])

    # --- sensitivity (seeds 1000-1029) --------------------------------------
    d3 = pick(sens, parameter="max_tree_depth", value="3")
    d8 = pick(sens, parameter="max_tree_depth", value="8")
    claim("Depth 3 -> 8: legit 83% -> 100%", near(float(d3["legit_completed_pct"]), 83.3, 0.1) and float(d8["legit_completed_pct"]) == 100.0, (d3["legit_completed_pct"], d8["legit_completed_pct"]))
    claim("Depth 3 -> 8: mean runaway $4.72 -> $6.84", near(float(d3["mean_runaway_usd"]), 4.72, 0.005) and near(float(d8["mean_runaway_usd"]), 6.84, 0.005), (d3["mean_runaway_usd"], d8["mean_runaway_usd"]))

    # --- cap sweep ---------------------------------------------------------
    exp_long = {0: 100, 2_000_000: 0, 4_000_000: 23, 8_000_000: 90, 16_000_000: 100}
    exp_cyc = {0: 15.18, 2_000_000: 6.11, 4_000_000: 12.18, 8_000_000: 15.18, 16_000_000: 15.18}
    for c in exp_long:
        a = pick(cap, family="long_var", cap=c)
        b = pick(cap, family="long_cycle", cap=c)
        claim(f"Cap sweep at {c}: long task {exp_long[c]}%, long cycle ${exp_cyc[c]}",
              int(a["completed_pct"]) == exp_long[c] and near(float(b["median_runaway_usd"]), exp_cyc[c], 0.005),
              (a["completed_pct"], b["median_runaway_usd"]))
    a = pick(cap, family="long_var", cap=2_000_000)
    claim("Graceful cap: killed long tasks left no half-finished writes", a["orphaned_writes"] == "0", a["orphaned_writes"])

    # --- ceiling only (hierarchical $ ceiling, no detectors) ---------------
    for fam in ("normal_var", "long_var", "batch_var", "wide_batch", "polling", "deep_delegation"):
        r = pick(ceil, family=fam, strategy="ceiling_100")
        claim(f"$100 tree ceiling completes every {fam} run", r["completed_pct"] == "100", r["completed_pct"])
    r = pick(ceil, family="deep_delegation", strategy="ceiling_50")
    claim("$50 ceiling: deep delegation 87%", r["completed_pct"] == "87", r["completed_pct"])
    r = pick(ceil, family="batch_var", strategy="ceiling_25")
    claim("$25 ceiling: small batches 60%", r["completed_pct"] == "60", r["completed_pct"])
    for fam, usd in (("retry_var", 99.37), ("recursive_var", 99.86), ("long_cycle", 99.50)):
        r = pick(ceil, family=fam, strategy="ceiling_100")
        claim(f"$100 ceiling: {fam} stops at about $100", near(float(r["median_runaway_usd"]), usd, 0.005), r["median_runaway_usd"])
    r = pick(rob, family="stuck_poll", guardrail="layered_v1")
    claim("v1 stops the endless poll for $0.18", near(float(r["median_runaway_usd"]), 0.18, 0.005), r["median_runaway_usd"])
    for fam, usd in (("slow_drip", 5.32), ("stuck_poll", 2.15)):
        r = pick(rob, family=fam, guardrail="layered_v2")
        claim(f"{fam}: ${usd} spent by the one-hour horizon", near(float(r["median_runaway_usd"]), usd, 0.005), r["median_runaway_usd"])

    # --- replay of real agent runs (needs the tau-bench traces; skipped if absent) ---
    if os.path.exists(R("replay.csv")):
        rep = load(R("replay.csv"))
        import json as _json
        summ = _json.load(open(R("replay_summary.json")))
        claim("Replay: 1,980 real runs, 1,183 successful", summ["runs"] == 1980 and summ["successful"] == 1183, (summ["runs"], summ["successful"]))
        r = pick(rep, detector="exact (tool + arguments)")
        claim("Exact matching fired on 0 successful real runs", r["fired_on_successful_n"] == "0", r["fired_on_successful_n"])
        r = pick(rep, detector="tool name only")
        claim("Name-only matching fired on 16 successful runs (1.4%)", r["fired_on_successful_n"] == "16", r["fired_on_successful_n"])
        r = pick(rep, detector="tool name only, all messages alike")
        claim("Collapsing all messages: false alarms about 20%", near(float(r["fired_on_successful_pct"]), 20.4, 0.05), r["fired_on_successful_pct"])
        r = pick(rep, detector="breaker")
        claim("Breaker never fired on real runs", r["fired_on_successful_n"] == "0" and r["fired_on_failed_n"] == "0", (r["fired_on_successful_n"], r["fired_on_failed_n"]))
        claim("Median 13 actions; no call repeated more than twice in a row", summ["median_actions"] == 13 and summ["max_identical_calls_in_a_row"] == 2,
              (summ["median_actions"], summ["max_identical_calls_in_a_row"]))
    else:
        print("note: results/replay.csv not found; skipping real-trace claims (see agentguard/replay.py)")

    if os.path.exists(R("replay_aider.csv")):
        import json as _json
        ra = load(R("replay_aider.csv"))
        sa = _json.load(open(R("replay_aider_summary.json")))
        claim("Aider: 300 runs, 79 resolved, 16 stuck (5 later resolved)",
              (sa["runs"], sa["resolved"], sa["stuck"], sa["stuck_resolved"]) == (300, 79, 16, 5),
              (sa["runs"], sa["resolved"], sa["stuck"], sa["stuck_resolved"]))
        r = pick(ra, detector="exact (tool + arguments)")
        claim("Aider: exact matching caught 0 of 16 stuck runs", r["fired_on_stuck_n"] == "0", r["fired_on_stuck_n"])
        r = pick(ra, detector="file name only")
        claim("Aider: file-name matching caught 14 of 16 stuck, fired on 20 of 79 resolved",
              (r["fired_on_stuck_n"], r["fired_on_resolved_n"]) == ("14", "20"), (r["fired_on_stuck_n"], r["fired_on_resolved_n"]))
        claim("Aider: a stuck run reached 106 actions", sa["stuck_max_actions"] == 106, sa["stuck_max_actions"])
        r = pick(ra, detector="breaker as simulated (5 in 60 s), real timestamps")
        claim("Aider: simulated breaker fired on 1 run at real pace", int(r["fired_on_resolved_n"]) + int(r["fired_on_unresolved_n"]) == 1,
              (r["fired_on_resolved_n"], r["fired_on_unresolved_n"]))
        r = pick(ra, detector="file name only")
        claim("Aider: name-only matching fired on 98 of 221 failed runs", r["fired_on_unresolved_n"] == "98", r["fired_on_unresolved_n"])
        r = pick(ra, detector="breaker as simulated (5 in 60 s), real timestamps")
        claim("Aider: 60 s breaker fired on 1 stuck-looking run, 1 failed, 0 succeeded",
              (r["fired_on_stuck_n"], r["fired_on_unresolved_n"], r["fired_on_resolved_n"]) == ("1", "1", "0"),
              (r["fired_on_stuck_n"], r["fired_on_unresolved_n"], r["fired_on_resolved_n"]))
        r = pick(ra, detector="breaker, 5 in 30 min, real timestamps")
        claim("Aider: 30-minute breaker caught 12 of 16 stuck, fired on 9 of 79 resolved and 69 of 221 unresolved",
              (r["fired_on_stuck_n"], r["fired_on_resolved_n"], r["fired_on_unresolved_n"]) == ("12", "9", "69"),
              (r["fired_on_stuck_n"], r["fired_on_resolved_n"], r["fired_on_unresolved_n"]))
        r = pick(ra, detector="exact (tool + arguments)")
        claim("Aider: exact matching fired once, on a resolved run", (r["fired_on_resolved_n"], r["fired_on_unresolved_n"]) == ("1", "0"),
              (r["fired_on_resolved_n"], r["fired_on_unresolved_n"]))
        claim("Aider: about 72 s per action", near(sa["median_seconds_per_action_between_timestamps"], 71.8, 0.05),
              sa["median_seconds_per_action_between_timestamps"])
    else:
        print("note: results/replay_aider.csv not found; skipping Aider claims")

    bad = [c for c in checks if not c[1]]
    for text, ok, got in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {text}  [{got}]")
    print(f"\n{len(checks) - len(bad)}/{len(checks)} claims match the result files.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
