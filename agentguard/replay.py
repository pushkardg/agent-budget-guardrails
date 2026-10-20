"""Replay real agent runs through the loop detectors (no simulator, no API calls).

    git clone --depth 1 https://github.com/sierra-research/tau-bench
    python -m agentguard.replay --traces tau-bench/historical_trajectories --out results

    # optional: 300 Aider coding-agent transcripts from SWE-bench Lite
    git clone --filter=blob:none --no-checkout https://github.com/SWE-bench/experiments
    (cd experiments && git sparse-checkout set --no-cone 'evaluation/lite/20240523_aider/*' && git checkout)
    python -m agentguard.replay --traces tau-bench/historical_trajectories \
        --aider experiments/evaluation/lite/20240523_aider --out results

tau-bench (MIT, Sierra) publishes 1,980 runs of GPT-4o and Claude 3.5 Sonnet
acting as customer-service agents with real tool calls, each labelled with
whether the task succeeded. This module feeds each run's actions, in order,
through the same NoveltyTracker and CircuitBreaker classes the simulator uses,
and reports where they would have fired.

What it measures:
  - False alarms: how often a detector would have stopped a run that succeeded.
  - Fingerprint choice: exact (tool + arguments, the simulator's choice) vs
    name-only (tool name, ignoring arguments: a crude stand-in for matching by
    meaning, which can't be fooled by rephrasing but should fire more often).
  - Real repetition in failed runs: identical calls repeated back to back.
  - Spend: estimated per-run cost against the layered design's $5 starting budget.

What it can't measure: these runs are short (median ~6 tool calls), so they
test false alarms on legitimate traffic, not detection of long real loops.
Replay is also open-loop: a real stop would have changed what came next.
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import hashlib
import json
import os
import statistics
from collections import Counter

from .breaker import CircuitBreaker
from .velocity import NoveltyTracker

FILES = {
    "gpt-4o-airline.json": ("GPT-4o", "airline"),
    "gpt-4o-retail.json": ("GPT-4o", "retail"),
    "sonnet-35-new-airline.json": ("Claude 3.5 Sonnet", "airline"),
    "sonnet-35-new-retail.json": ("Claude 3.5 Sonnet", "retail"),
}
STEP_S = 3.0  # assumed seconds per agent step, for the breaker's time window
IN_USD, OUT_USD = 3.0, 15.0  # same illustrative prices as the simulator, per million tokens


def tokens(text: str) -> int:
    return max(1, len(text) // 4)  # rough chars-per-token estimate


def actions(traj: list[dict]) -> list[tuple[str, str, str, bool]]:
    """(kind, name, canonical args, failed) for each agent action, in order.
    kind is 'tool' or 'say' (a message to the user)."""
    results = {m.get("tool_call_id"): (m.get("content") or "") for m in traj if m.get("role") == "tool"}
    out = []
    for m in traj:
        if m.get("role") != "assistant":
            continue
        calls = m.get("tool_calls") or []
        if not calls:
            out.append(("say", "say", (m.get("content") or "").strip(), False))
            continue
        for c in calls:
            fn = c.get("function", {})
            raw = fn.get("arguments") or "{}"
            try:
                args = json.dumps(raw if isinstance(raw, dict) else json.loads(raw), sort_keys=True)
            except json.JSONDecodeError:
                args = str(raw)
            failed = results.get(c.get("id"), "").lower().startswith("error")
            out.append(("tool", fn.get("name", "?"), args, failed))
    return out


def fingerprint(a: tuple[str, str, str, bool], mode: str) -> str:
    kind, name, args, _ = a
    if mode == "exact":
        return f"{name}:{args}"
    if mode == "name":  # tool name, ignoring arguments; messages to the user still compared by text
        return name if kind == "tool" else f"say:{args}"
    return name  # "name_all": also treats every message to the user as the same action


def novelty_fires(acts, mode: str, window: int, min_samples: int, floor: float):
    """Index of the first action at which the novelty detector would stop the run, else None."""
    t = NoveltyTracker(window, min_samples)
    for i, a in enumerate(acts):
        t.add(fingerprint(a, mode))
        r = t.ratio()
        if r is not None and r < floor:
            return i
    return None


def breaker_fires(acts, threshold=5, window_s=60.0, cooldown_s=120.0, max_rejections=3, step_s=STEP_S, tools=None, times=None):
    """Index at which the run-level breaker rule would stop the run, else None."""
    breakers: dict[str, CircuitBreaker] = {}
    rejections = 0
    for i, (kind, name, _, failed) in enumerate(acts):
        if kind != "tool" or (tools is not None and not name.startswith(tools)):
            continue
        now = times[i] if times is not None else i * step_s
        b = breakers.setdefault(name, CircuitBreaker(threshold, window_s, cooldown_s))
        if not b.allow(now):
            rejections += 1
            if rejections >= max_rejections:
                return i
            continue
        (b.record_failure if failed else b.record_success)(now)
    return None


def longest_repeat(acts) -> int:
    best = run = 0
    prev = None
    for a in acts:
        if a[0] != "tool":
            prev, run = None, 0
            continue
        key = (a[1], a[2])
        run = run + 1 if key == prev else 1
        prev = key
        best = max(best, run)
    return best


def est_cost_usd(traj: list[dict]) -> float:
    """Each assistant turn re-reads the whole conversation so far (input) and writes its own message (output)."""
    ctx = cost = 0.0
    for m in traj:
        body = (m.get("content") or "") + json.dumps(m.get("tool_calls") or "")
        n = tokens(body)
        if m.get("role") == "assistant":
            cost += ctx * IN_USD / 1e6 + n * OUT_USD / 1e6
        ctx += n
    return cost


CONFIGS = [  # (label, fingerprint mode, window, min_samples, floor)
    ("exact (tool + arguments)", "exact", 20, 10, 0.4),
    ("tool name only", "name", 20, 10, 0.4),
    ("tool name only, all messages alike", "name_all", 20, 10, 0.4),
    ("exact, tighter window (10/5)", "exact", 10, 5, 0.4),
]


# --- Aider coding-agent transcripts (SWE-bench Lite, May 2024) -------------------
def _h(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:10]


def aider_actions(path: str) -> list[tuple[str, str, str, bool]]:
    """Actions from one Aider chat transcript, in order.

    - Each SEARCH/REPLACE block the model proposes is a tool call 'edit:<file>'
      whose arguments are a hash of the block. It's marked failed if Aider later
      reports that block's SEARCH text didn't match the file.
    - Each 'Attempt to fix test errors?' is a failed 'run_tests' call.
    - Each new chat session (the harness retrying the task) is a 'say' action.
    """
    lines = open(path, encoding="utf-8").read().split("\n")
    acts: list[list] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("<<<<<<< SEARCH"):
            fname = lines[i - 2].strip() if i >= 2 else "?"
            j, search, replace = i + 1, [], []
            while j < len(lines) and not lines[j].startswith("======="):
                search.append(lines[j].rstrip())
                j += 1
            j += 1
            while j < len(lines) and not lines[j].startswith(">>>>>>> REPLACE"):
                replace.append(lines[j].rstrip())
                j += 1
            s = "\n".join(search)
            acts.append(["tool", f"edit:{fname}", _h(s + "\n=\n" + "\n".join(replace)), False, _h(s)])
            i = j + 1
            continue
        if line.startswith("> <<<<<<< SEARCH"):  # Aider quoting a block that failed to match
            j, quoted = i + 1, []
            while j < len(lines) and not lines[j].startswith("> ======="):
                q = lines[j]
                quoted.append((q[2:] if q.startswith("> ") else q).rstrip())
                j += 1
            qh = _h("\n".join(quoted))
            for a in reversed(acts):
                if a[4] == qh and not a[3]:
                    a[3] = True
                    break
            i = j
            continue
        if line.startswith("> Attempt to fix test errors"):
            acts.append(["tool", "run_tests", "", True, None])
        elif line.startswith("# aider chat started"):
            acts.append(["say", "session_start", str(len(acts)), False, None])
        i += 1
    return [tuple(a[:4]) for a in acts]


def aider_times(path: str, acts) -> list[float] | None:
    """Seconds since the first session for each action, interpolated between the
    'aider chat started at' timestamps. The last session uses the median pace
    of the run's earlier sessions (or 80 s per action, the corpus median)."""
    import datetime
    stamps = [datetime.datetime.strptime(m, "%Y-%m-%d %H:%M:%S") for m in
              re.findall(r"^# aider chat started at (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)",
                         open(path, encoding="utf-8").read(), re.M)]
    starts = [i for i, a in enumerate(acts) if a[1] == "session_start"]
    if not stamps or len(stamps) != len(starts):
        return None
    t0 = stamps[0]
    secs = [(s - t0).total_seconds() for s in stamps]
    paces = []
    for k in range(len(starts) - 1):
        n = starts[k + 1] - starts[k]
        if n > 0 and secs[k + 1] > secs[k]:
            paces.append((secs[k + 1] - secs[k]) / n)
    default = statistics.median(paces) if paces else 80.0
    times = [0.0] * len(acts)
    for k, st in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(acts)
        n = end - st
        pace = ((secs[k + 1] - secs[k]) / n) if (k + 1 < len(starts) and n and secs[k + 1] > secs[k]) else default
        for j in range(st, end):
            times[j] = secs[k] + (j - st) * pace
    return times


def stuck(acts) -> bool:
    """Independent label for a clearly stuck run: the identical failing edit proposed 3+ times."""
    c = Counter((n, x) for k, n, x, f in acts if f and n.startswith("edit"))
    return max(c.values(), default=0) >= 3


def run_aider(directory: str, out: str) -> None:
    resolved = set(json.load(open(os.path.join(directory, "results", "results.json")))["resolved"])
    runs = []
    for p in sorted(glob.glob(os.path.join(directory, "chat-transcripts", "*.md"))):
        acts = aider_actions(p)
        runs.append({"ok": os.path.basename(p)[:-3] in resolved, "acts": acts, "stuck": stuck(acts),
                     "times": aider_times(p, acts)})
    ok = [r for r in runs if r["ok"]]
    bad = [r for r in runs if not r["ok"]]
    stk = [r for r in runs if r["stuck"]]
    detectors = {
        "exact (tool + arguments)": lambda a: novelty_fires(a, "exact", 20, 10, 0.4),
        "exact, tighter window (10/5)": lambda a: novelty_fires(a, "exact", 10, 5, 0.4),
        "file name only": lambda a: novelty_fires(a, "name", 20, 10, 0.4),
        "breaker as simulated (5 in 60 s), real timestamps": lambda r: breaker_fires(r["acts"], times=r["times"]),
        "breaker, 5 in 30 min, real timestamps": lambda r: breaker_fires(r["acts"], window_s=1800.0, cooldown_s=3600.0, times=r["times"]),
        "breaker, 5 in 30 min, edits only": lambda r: breaker_fires(r["acts"], window_s=1800.0, cooldown_s=3600.0, tools=("edit",), times=r["times"]),
    }
    timed = [r for r in runs if r["times"] is not None]
    rows = []
    for label, fn in detectors.items():
        pool = timed if "timestamps" in label or "edits only" in label else runs
        f = (lambda r, fn=fn: fn(r)) if pool is timed else (lambda r, fn=fn: fn(r["acts"]))
        rows.append({"detector": label,
                     "fired_on_resolved_n": sum(f(r) is not None for r in pool if r["ok"]),
                     "fired_on_unresolved_n": sum(f(r) is not None for r in pool if not r["ok"]),
                     "fired_on_stuck_n": sum(f(r) is not None for r in pool if r["stuck"]),
                     "runs": len(pool)})
    edits = [a for r in runs for a in r["acts"] if a[1].startswith("edit")]
    summary = {
        "runs": len(runs), "resolved": len(ok), "unresolved": len(bad), "stuck": len(stk),
        "stuck_resolved": sum(r["ok"] for r in stk),
        "median_actions": statistics.median(len(r["acts"]) for r in runs),
        "max_actions": max(len(r["acts"]) for r in runs),
        "stuck_min_actions": min(len(r["acts"]) for r in stk), "stuck_max_actions": max(len(r["acts"]) for r in stk),
        "edits": len(edits), "failed_edits": sum(a[3] for a in edits),
        "failed_test_rounds": sum(a[1] == "run_tests" for r in runs for a in r["acts"]),
        "max_identical_calls_in_a_row": max(longest_repeat(r["acts"]) for r in runs),
        "runs_with_usable_timestamps": len(timed),
        "median_seconds_per_action_between_timestamps": round(statistics.median(
            (r["times"][st2] - r["times"][st1]) / (st2 - st1)
            for r in timed
            for st1, st2 in zip([i for i, a in enumerate(r["acts"]) if a[1] == "session_start"],
                                [i for i, a in enumerate(r["acts"]) if a[1] == "session_start"][1:])
            if r["times"][st2] > r["times"][st1]), 1),
    }
    with open(os.path.join(out, "replay_aider.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out, "replay_aider_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    lines = [
        "# Replay of real coding-agent runs (Aider on SWE-bench Lite, May 2024)",
        "",
        f"{len(runs)} runs: {len(ok)} resolved, {len(bad)} unresolved. "
        f"'Stuck' = the identical failing edit proposed 3+ times ({len(stk)} runs, {summary['stuck_resolved']} of them later resolved).",
        "",
        f"| Detector | Fired on resolved ({len(ok)}) | Fired on unresolved ({len(bad)}) | Fired on stuck ({len(stk)}) |",
        "|---|---|---|---|",
    ] + [f"| {r['detector']} | {r['fired_on_resolved_n']} | {r['fired_on_unresolved_n']} | {r['fired_on_stuck_n']} |" for r in rows] + [
        "",
        "Exact = edit file plus a hash of the proposed change. File name only = ignores the change. "
        "Breaker rows use each action's time interpolated between the transcript's session timestamps "
        f"({len(timed)} runs with usable timestamps). The simulated breaker opens after 5 failures of one tool in 60 s.",
        "",
        "## Run shape",
        "",
    ] + [f"- {k.replace('_', ' ')}: {v}" for k, v in summary.items()] + [
        "",
        "Aider's own limits (a few reflections per session, a few sessions per task) already bound these runs, "
        "so they can't contain unbounded runaways. Replay is open-loop.",
    ]
    with open(os.path.join(out, "replay_aider.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True, help="tau-bench historical_trajectories directory")
    ap.add_argument("--aider", help="SWE-bench experiments evaluation/lite/20240523_aider directory (optional)")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    runs = []
    for fname, (model, domain) in FILES.items():
        for r in json.load(open(os.path.join(args.traces, fname))):
            acts = actions(r["traj"])
            runs.append({
                "model": model, "domain": domain, "ok": r["reward"] >= 0.5, "acts": acts,
                "n_tool": sum(a[0] == "tool" for a in acts), "n_act": len(acts),
                "n_fail": sum(a[3] for a in acts), "repeat": longest_repeat(acts),
                "cost": est_cost_usd(r["traj"]),
                **{c[0]: novelty_fires(acts, *c[1:]) for c in CONFIGS},
                "breaker": breaker_fires(acts),
            })

    ok = [r for r in runs if r["ok"]]
    bad = [r for r in runs if not r["ok"]]
    pct = lambda xs, f: 100 * sum(1 for x in xs if f(x)) / len(xs)  # noqa: E731
    rows = []
    for label in [c[0] for c in CONFIGS] + ["breaker"]:
        rows.append({
            "detector": label,
            "fired_on_successful_pct": round(pct(ok, lambda r: r[label] is not None), 1),
            "fired_on_successful_n": sum(r[label] is not None for r in ok),
            "fired_on_failed_pct": round(pct(bad, lambda r: r[label] is not None), 1),
            "fired_on_failed_n": sum(r[label] is not None for r in bad),
        })
    eligible = pct(runs, lambda r: r["n_act"] >= 10)
    costs = sorted(r["cost"] for r in runs)
    summary = {
        "runs": len(runs), "successful": len(ok), "failed": len(bad),
        "median_actions": statistics.median(r["n_act"] for r in runs),
        "max_actions": max(r["n_act"] for r in runs),
        "median_tool_calls": statistics.median(r["n_tool"] for r in runs),
        "pct_runs_with_10plus_actions": round(eligible, 1),
        "runs_with_any_tool_error": sum(r["n_fail"] > 0 for r in runs),
        "failed_runs_with_3plus_identical_calls_in_a_row": sum(r["repeat"] >= 3 for r in bad),
        "successful_runs_with_3plus_identical_calls_in_a_row": sum(r["repeat"] >= 3 for r in ok),
        "max_identical_calls_in_a_row": max(r["repeat"] for r in runs),
        "median_est_cost_usd": round(statistics.median(costs), 3),
        "max_est_cost_usd": round(costs[-1], 3),
        "runs_over_5_usd": sum(c > 5 for c in costs),
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "replay.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "replay_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    by_model = Counter((r["model"], r["domain"]) for r in runs)
    lines = [
        "# Replay of real agent runs (tau-bench historical trajectories)",
        "",
        f"{len(runs)} runs ({len(ok)} successful, {len(bad)} failed): "
        + ", ".join(f"{m} {d} {n}" for (m, d), n in sorted(by_model.items())) + ".",
        "",
        "| Detector | Fired on successful runs | Fired on failed runs |",
        "|---|---|---|",
    ] + [f"| {r['detector']} | {r['fired_on_successful_pct']}% ({r['fired_on_successful_n']}) | "
         f"{r['fired_on_failed_pct']}% ({r['fired_on_failed_n']}) |" for r in rows] + [
        "",
        "Exact = tool name plus arguments (the simulator's fingerprint). Tool name only = ignores arguments, "
        "a crude stand-in for matching by meaning; messages to the user are still compared by text. "
        "'All messages alike' also treats every message to the user as one repeated action. Breaker = run-level circuit-breaker rule "
        f"(5 failures of one tool, then 3 rejected calls), assuming {STEP_S:.0f} s per step.",
        "",
        "## Run shape",
        "",
    ] + [f"- {k.replace('_', ' ')}: {v}" for k, v in summary.items()] + [
        "",
        "Replay is open-loop: it shows where a detector would have fired, not what the agent would have done next. "
        "These runs are short, so this tests false alarms on legitimate work, not detection of long real loops.",
    ]
    with open(os.path.join(args.out, "replay.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    if args.aider:
        print()
        run_aider(args.aider, args.out)


if __name__ == "__main__":
    main()
