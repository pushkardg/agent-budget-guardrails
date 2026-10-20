# agentguard: budget guardrails for autonomous agents

An agent stuck in a loop doesn't fail loudly. It just keeps spending. This repo is a small,
dependency-free reference implementation of layered spend guardrails for agents, plus a
deterministic simulator that throws runaway and legitimate agent workloads at different
guardrail strategies and measures what happens, including where the guardrails fail.

No real models are called. Agents are scripted, prices are illustrative
($3 / $15 per million input / output tokens), and every run is reproducible.

```bash
python -m agentguard.bench --out results        # fixed scenarios, ablation, billing  (<1 s)
python -m agentguard.robustness --out results   # randomized suite + sensitivity sweep (~30 s)
python -m agentguard.capsweep --out results     # v2 plus a token cap at 4 levels (~1 min)
python -m agentguard.ceilingsweep --out results # dollar ceiling per run tree, no detectors (~1 min)
python -m agentguard.replay --traces tau-bench/historical_trajectories --out results  # real agent runs (see below)
python -m agentguard.overhead --out results     # ledger bookkeeping cost
python -m agentguard.verify_claims              # checks the article's numbers against results/
python -m pytest -q                             # 31 tests
```

Requires Python 3.10+. No runtime dependencies.

## How to read these results

The same person wrote the guardrails and the scenarios, so a table where the guardrails
win every row would prove little. The evaluation is set up to push against that:

1. **Fixed scenarios** (`scenarios.py`) illustrate the main failure modes.
2. **Randomized families** (`variants.py`) draw scenario shapes from a seeded RNG. Several
   were written specifically to break the design.
3. **v1 → v2 → v3, each on seeds the previous step never saw:**

   | Seeds | Used for |
   |---|---|
   | 0–29 | Developing v2 from v1's failures |
   | 1000–1029 | Evaluating v2, and the sensitivity sweep that led to v3 |
   | 2000–2029 | Final evaluation of v1, v2 and v3 (the default `robustness` run; the article's tables) |

4. **New adversarial families were written after v2** to break the v2 fixes, and they do.
5. **Sensitivity sweep** varies each threshold to show the operating range rather than a
   single tuned point.

Every experiment behind the article:

| Experiment | Workloads | Strategies | Runs |
|---|---|---|---|
| Development | Randomized families, seeds 0–29 | v1 | Not reported; used to build v2 |
| Fixed scenarios and ablation | 6 hand-written scenarios | All 7, plus 6 ablation variants | 78 |
| Sensitivity sweep and check | 13 families × 30 seeds (1000–1029) | 23 settings of v2, plus 6 strategies | 11,310 |
| Final evaluation | 13 families × 30 seeds (2000–2029) | All 7 | 2,730 |
| Token cap on top of v2 | Same families and seeds | v2 with 4M, 8M, 16M caps (2M is one of the 7) | 1,170 |
| Dollar ceiling only | Same families and seeds | $25, $50, $100 ceilings | 1,170 |

About 16,500 runs in total. Most are the sensitivity sweep; the article's main tables rest on the 2,730-run final evaluation.

## What's being compared

| Strategy | What it does |
|---|---|
| `none` | Nothing. Spend is observed only. |
| `monthly_alert` | The common default: alert at 80% of a $200 monthly tenant budget, seen through a usage pipeline with a 30-minute reporting delay. Never stops anything. |
| `static_token_cap` | 2M tokens per run, enforced by a watchdog that hard-kills the run. |
| `layered_v1` | The layered design below. |
| `layered_v2` | v1 plus fixes for the failures the randomized suite found. |
| `v2_plus_cap` | v2 with the 2M-token per-run cap kept on top, stopped gracefully. `capsweep` repeats this at 4M, 8M and 16M. |
| `ceiling_N` | The simplest baseline: a hierarchical dollar ceiling of $N per run tree, with reservations and hierarchy on and every detector, extension and throttle off (`ceiling_only_config`). Run by `ceilingsweep` at $25, $50 and $100. |
| `layered_v3` | v2 with tree depth 8, the change the v2 sensitivity sweep pointed to (see below). Proposed, not validated outside simulation. |

## The layered design

1. **Reservations against hierarchical budgets** (`ledger.py`). Holds can carry a lease;
   `sweep_expired()` frees holds whose caller crashed, and a settle that arrives after expiry
   still records the spend (`late_settles`) for reconciliation. One lock makes check-and-hold
   atomic across the chain; tests cover concurrent reservations, crashes and late settles.
   `renew()` extends a lease while a call is still running. Expiry trades strict enforcement
   for liveness: if a lease expires while the call is actually still running, its budget can be
   re-reserved and total spend can briefly exceed the limit. Keep leases longer than the
   provider request deadline, renew while streaming, and treat any expiry as an alert. Before every model call the
   agent must hold its worst-case cost (known input tokens + max output tokens), like a card
   pre-authorization. Budgets form a tree: tenant → root run → child run. A hold must fit at
   every level, so a run's budget covers all of its descendants.
2. **Health-gated budget extensions.** When a run hits its budget ($5 to start), it is doubled
   only if its whole subtree looks healthy: no loop signal, no open circuit, normal spend rate,
   bounded tree.
3. **Loop detection by action novelty** (`velocity.py`). The fraction of distinct actions in
   recent steps. Identical retries and short plan cycles drive it toward zero.
4. **Velocity throttling.** Spend rate per run and per tenant over a sliding window.
   Exceeding it applies backpressure (delay), not a kill.
5. **Circuit breakers** (`breaker.py`), per tenant and tool. When an agent keeps calling a
   tool whose circuit is open, a run-level breaker stops the run, because the model call that
   decides to retry still costs money even when the tool call is rejected.
6. **Graceful stops** (`stop.py`). Side-effecting tool calls are two-phase (stage, then
   commit). A graceful stop compensates anything staged; a hard kill leaves it orphaned. Stops
   propagate to the whole subtree.

**v2 changes** (`layered_v2_config()` in `controllers.py`), each aimed at a v1 failure:

| v1 failure | v2 change |
|---|---|
| Long planning cycles hid inside the 20-step novelty window | Second novelty window of 100 steps |
| Legitimate wide fan-out (17–40 workers) was denied extensions | Tree health checks **depth** (recursion grows deep, fan-out grows wide); size limit relaxed to 256 |
| A run that fools every signal could extend to $160 | Absolute ceiling: no run tree past $100 (half the tenant budget) without a human |
| Polling a job status looked like a loop | Actions declared as waits (`poll:`) are exempt from novelty |

## Results: fixed scenarios (60-minute horizon)

| Runaway | none | monthly_alert | static_token_cap | layered (v1 = v2 here) |
|---|---|---|---|---|
| Retry loop | $199, never stops | alert at 79 min | $6.10, 3.6 min | **$0.68, 42 s** |
| Recursive spawning | $428 in 101 s | alert ~29 min after the spend | never fires | **$4.88, 26 s** |
| Cycling planner | $141, never stops | never | $6.26, 5.2 min, 1 orphaned write | **$2.09, 2.7 min** |

v3 matches v1 and v2 on these fixed scenarios except recursive spawning, where it spends $19.87
and takes 2.6 min to contain, the same 4x regression the randomized suite shows.

Legitimate work: the static cap killed the 300-step task at ~1/3 done with an orphaned write.
Both layered versions completed everything. Full tables in
[`results/results.md`](results/results.md); v1 ablation in [`results/ablation.md`](results/ablation.md).

## v3: the configuration the sensitivity sweep pointed to

The v2 sweep (seeds 1000–1029) said tree depth 3 was too tight and depth 8 cost little.
`layered_v3_config()` is v2 with depth 8, evaluated on seeds **2000–2029**, which no design
decision has looked at (`python -m agentguard.robustness`, the default).

| Family | v2 | v3 |
|---|---|---|
| deep_delegation (legit), % completed | 0% (CI 0–11%) | **100%** (CI 89–100%), 40% slower |
| recursive_var, median runaway spend / time to contain | $4.86 / 26 s | **$19.85 / 152 s** |
| everything else | unchanged | unchanged |

The sweep reported mean runaway spend across all families rising from $4.72 to $6.84. That
average hid a **4x** cost regression on the one family hierarchical budgets exist for. Read
per-family results, not averages.

## Keeping the token cap on top of v2

`python -m agentguard.capsweep` runs v2 with a per-run token cap (graceful stop) at 2M, 4M, 8M and 16M tokens, on seeds 2000-2029. Full table: [`results/cap_sweep.md`](results/cap_sweep.md).

| On top of v2 | No cap | 2M | 4M | 8M | 16M |
|---|---|---|---|---|---|
| Long legitimate task, % completed | 100% | 0% | 23% | 90% | 100% |
| Long planning cycle, median spend to stop | $15.18 | $6.11 | $12.18 | $15.18 | $15.18 |

No cap level stops long cycles sooner without also killing long legitimate tasks: in token terms they look the same. Because the stop is graceful, the killed tasks leave no half-finished writes.

## Dollar ceiling only, no detectors

`python -m agentguard.ceilingsweep` runs `Layered(ceiling_only_config(N))` at $25, $50 and $100 on seeds 2000-2029, next to v2. Full table: [`results/ceiling_sweep.md`](results/ceiling_sweep.md).

- At $100 it completes every legitimate run in all six families, including deep delegation, which v2 kills.
- Tighter ceilings start killing real work: $50 completes 87% of deep delegation, $25 completes 60% of small batches.
- Every runaway it stops spends the whole ceiling (~$99 for a retry loop v2 stops for $0.65; ~$15 vs ~$99 for long cycles).
- Recursion under a $100 ceiling counts as only 50% contained: it spends ~$99.86, but half the runs hit the simulator's 2,000-agent safety cap first.

So the detectors buy stops roughly 7–150x cheaper, at the price of false positives. v2 is exactly a $100 tree ceiling with detectors on top.

## Why v3 makes recursion 4x costlier

Under v2 (depth ≤ 3) a recursive tree passes depth 3 almost immediately, so it is never extended (median 0 extensions) and stops at ~97 agents. Under v3 (depth ≤ 8) it looks healthy for longer, collects a median of 5 extensions, and grows to ~390 agents before it stops (seeds 2000-2029).

## Provider errors at the gateway

The article's gateway snippet releases the hold on errors that were definitely not billed (a 429, a rejected request) and keeps it, with a renewed lease, only on ambiguous ones (timeouts, dropped streams), until reconciliation settles it. Holding money on every error would let a burst of rate-limit errors lock a run's budget and stop it falsely. The simulator does not model provider errors, so this path is untested here.

## Replaying real agent runs

The simulator's agents are scripts. To check the loop detectors against real model behaviour, `replay.py` feeds recorded runs through the same `NoveltyTracker` and `CircuitBreaker` classes, offline, with no API calls:

```bash
git clone --depth 1 https://github.com/sierra-research/tau-bench
python -m agentguard.replay --traces tau-bench/historical_trajectories --out results
```

[tau-bench](https://github.com/sierra-research/tau-bench) (MIT, Sierra) publishes 1,980 runs of GPT-4o and Claude 3.5 Sonnet as airline and retail customer-service agents, with real tool calls and a success label per run. Results ([`results/replay.md`](results/replay.md)):

| Detector | Fired on successful runs (1,183) | Fired on failed runs (797) |
|---|---|---|
| Novelty, exact (tool + arguments) | 0 (95% CI 0–0.3%) | 0 |
| Novelty, tool name only | 16 (1.4%) | 16 (2.0%) |
| Novelty, tool name only, all messages alike | 241 (20.4%) | 308 (38.6%) |
| Run-level breaker | 0 | 0 |

- All 16 name-only false alarms were an agent looking up a customer's reservations one after another: legitimate queue work that looks like a loop once arguments are ignored.
- What this can't show is detection. The runs are short (median 13 actions, max 30), the failures are wrong answers rather than loops (no run repeats an identical call more than twice in a row), and the most expensive run costs an estimated $0.69. This is evidence about false alarms on real agents, not about catching real loops.
- Replay is open-loop: it shows where a detector would have fired, not what the agent would have done after a stop.
- `verify_claims` checks these numbers when `results/replay.csv` is present and skips them otherwise.

### Real coding-agent runs (Aider, SWE-bench Lite)

The SWE-bench experiments repository on GitHub includes Aider's 300 chat transcripts from SWE-bench Lite (May 2024). Other submissions keep their trajectories on S3 or Hugging Face.

```bash
git clone --filter=blob:none --no-checkout https://github.com/SWE-bench/experiments
(cd experiments && git sparse-checkout set --no-cone 'evaluation/lite/20240523_aider/*' && git checkout)
python -m agentguard.replay --traces tau-bench/historical_trajectories \
    --aider experiments/evaluation/lite/20240523_aider --out results
```

Each proposed SEARCH/REPLACE edit becomes an action (file + hash of the change), marked failed when Aider reports it didn't match; each "fix test errors" round is a failed `run_tests` call. "Stuck-looking" is labelled independently: the identical failing edit proposed 3+ times. It marks repetition, not a proven runaway: 5 of the 16 were eventually resolved. Results ([`results/replay_aider.md`](results/replay_aider.md)):

| Detector | Resolved (79) | Unresolved (221) | Stuck (16) |
|---|---|---|---|
| Novelty, exact | 1 | 0 | 0 |
| Novelty, exact, window 10/5 | 1 | 2 | 0 |
| Novelty, file name only | 20 | 98 | 14 |
| Breaker as simulated (5 in 60 s), real time | 0 | 1 | 1 |
| Breaker, 5 in 30 min, real time | 9 | 69 | 12 |
| Breaker, 5 in 30 min, failed edits only | 3 | 11 | 5 |

- Exact matching misses every stuck run: the repeated failing edit sits among other, slightly different attempts, so novelty never drops far enough. Stuck runs ran 7 to 106 actions.
- File-name matching catches 14 of 16 but fires on 20 of 79 resolved runs, and 5 of the 16 stuck runs were eventually resolved.
- Breaker rows use approximate real time: the transcripts only timestamp each new session, so each action's time is interpolated evenly between the transcript's session timestamps (297 of 300 runs usable; about 72 s per action). The breaker as simulated (5 failures of one tool in 60 s) almost never opens at that pace: 1 run of 297. Widened to 5 failures in 30 minutes, it catches 12 of 16 stuck runs but fires on 9 of 79 resolved ones. Counting only failed edits (not failing test rounds) it catches 5 stuck runs and fires on 3 resolved ones.
- Aider's own retry limits bound every run, so these can't contain unbounded runaways.
- All replay results are counterfactual: they show where a detector would have stopped a run, not what would have happened after the stop.

## Live test with a real model (not yet run at scale)

`live.py` runs real model agents against planted faults, with every model call going through the real `Ledger` (reserve the worst case, settle from the usage the API reports) and the v2 detectors, using wall-clock time:

| Scenario | Kind | What's planted |
|---|---|---|
| `failing_tool` | runaway | a payments API that always returns 503, and a task that says to keep trying |
| `pagination_leak` | runaway | a listing API that never runs out of pages |
| `recursive_delegation` | runaway | a delegate tool and a task that tells every agent to split and delegate |
| `file_queue` | legitimate | read 15 different files, then summarize |
| `polling` | legitimate | poll a job that finishes after 8 checks |

```bash
python -m agentguard.live --fake --runs 1          # check the harness: scripted model, no network, no cost
export ANTHROPIC_API_KEY=...
python -m agentguard.live --model <model-id> --in-price <$/M in> --out-price <$/M out> --runs 3 --out results/live
```

By default it observes: detectors record when they would have stopped each run, and the run continues to a hard safety cap ($1 per run tree, 40 steps per agent, 24 agents), so the output shows both detection and the spend a stop would have saved. `--enforce` stops at the first detector. The script prints its worst-case total before starting ($15 with the defaults). Results go to `trace.jsonl` (timestamped, one line per call) and `summary.md`. The article reports no live results yet.

## Overhead

`python -m agentguard.overhead` times one reserve plus settle on the in-memory ledger: a few microseconds per call ([`results/overhead.md`](results/overhead.md)). That is the logic only. A production gateway adds a round trip to a shared store on every model call, which will dominate.

## Statistical note

Each family has 30 runs per strategy. Tables in `results/robustness.md` include 95% Wilson
score intervals: 30 of 30 contained means the true containment rate is very likely above
~89%, not that it is 100%; 0 of 30 means very likely below ~11%.

## Results: randomized families, seeds 1000–1029 (v1 and v2 evaluation)

`*` = written to break v1. `**` = written after v2, to break v2.

**Legitimate work, % completed** (orphaned writes in brackets where nonzero):

| Family | static cap | v1 | v2 |
|---|---|---|---|
| normal_var | 100 | 100 | 100 |
| long_var (100–400 steps) | **7** (28) | 100 | 100 |
| batch_var (3–12 workers) | 97 (4) | 100 | 100 |
| wide_batch* (17–40 workers) | 100 | **0** | 100, but **~2x wall time** from throttling |
| polling* | 100 | **0** | 100 |
| deep_delegation** (4–6 levels) | 100 | 57 | **0** |

**Runaways, % contained within the hour** (median runaway spend):

| Family | static cap | v1 | v2 |
|---|---|---|---|
| retry_var | 100 ($5.94) | 100 ($0.67) | 100 ($0.67) |
| retry_varying* (args change every attempt) | 100 ($5.94) | 100 ($0.67) | 100 ($0.67) |
| recursive_var | **0** ($285) | 100 ($4.87) | 100 ($4.87) |
| cycle_var (2–8 step cycles) | 100 ($6.07, 21 orphaned) | 90 (p95 **$114**) | 100 (p95 $8.83) |
| long_cycle* (12–30 step cycles) | 100 ($6.07, 11 orphaned) | **0** ($114) | 100 (**$16.75**) |
| slow_drip* (endless pagination) | 3 ($5.30) | 0 ($5.30) | 0 ($5.30) |
| stuck_poll** (job never finishes) | 0 ($2.16) | 100 ($0.18) | **0** ($2.16) |

Unguarded, these runaways spend $2–$285 per hour each. Full table with confidence intervals:
[`results/seeds_1000/robustness.md`](results/seeds_1000/robustness.md). The default run
(`results/robustness.md`) uses fresh seeds 2000–2029 and includes v3; v1 and v2 results there
have the same pattern with different draws (for example, v1 completes 50% of deep-delegation
runs there vs 57% here, and the static cap 0% of long tasks vs 7%).

## Sensitivity (v2, one threshold at a time)

From [`results/sensitivity.md`](results/sensitivity.md):

- **Containment did not move.** At every setting tested, v2 contained the same 5 of 7 runaway
  families and missed `slow_drip` and `stuck_poll`. Thresholds changed *how much* a contained
  runaway cost and *how often* legitimate work was killed, not *whether* a runaway class was
  caught.
- **The long novelty window matters most for cost.** Mean runaway spend: $17.86 with it off,
  $10.49 at 50 steps, $4.72 at 100, $6.49 at 200.
- **Tree depth 3 was too tight.** Depth 8 completed 100% of legitimate work (vs 83%) with mean
  runaway spend rising only from $4.72 to $6.84. The default was a guess, and the sweep shows
  it was the wrong one.
- **The run ceiling trades directly against big jobs.** $25 killed 35% of legitimate work;
  $100 and $200 killed none on this suite.
- Novelty floor (0.2–0.6) and breaker sensitivity (1–10 rejections) barely changed anything.

## Billing

Provider cost is always the full spend; the question is who absorbs it
([`results/billing.md`](results/billing.md)). With graceful stops you can identify the spend on
rolled-back work and choose not to bill it ($4.94 → $4.09 for the recursive case). With a hard
kill there is no record of what was discarded, so the only options are to bill all of it or
absorb all of it.

## Findings

1. **Monthly budget alerts do not protect against runaway agents.** By the time usage data
   lands, the money is gone.
2. **Static per-run caps are a better backstop than they look.** They contained every
   single-agent loop whose context grows (retries, short and long plan cycles) for about $6,
   including long cycles that fooled v1. Their costs: they
   killed 93% of long legitimate tasks, hard kills leave orphaned writes, and they are blind to
   fan-out (0% of recursive spawns contained).
3. **Budgets have to be hierarchical.** In the v1 ablation it was the only layer that stopped
   recursive spawning, and both layered versions contained 100% of randomized recursive
   spawns, where the static cap contained none.
4. **Breakers should key on the tool, not the call.** Retries with changing arguments had
   unique fingerprints but still hit the same failing tool, and were caught just as fast.
5. **Every loop detector has a cycle length it cannot see.** A 20-step window missed 12–30
   step cycles; a 100-step window catches them but only after ~$17, roughly 3x what the
   static cap spent. Keep a hard ceiling under any smart detector; they are complements.
6. **Every fix moved the failure boundary.** Exempting polling from loop detection made stuck
   polls invisible. Checking depth instead of size made deep legitimate delegation fail.
   There is no setting that is right for all workloads.
7. **Cheap leaks escape runtime detection.** Endless pagination at ~$5/hour was missed by
   every strategy within the hour, but it is ~$3,800/month per stuck agent. That needs a
   different control: periodic review of long-lived runs, not a runtime signal.
8. **Throttling is backpressure, not detection.** It never stopped a runaway on its own, and
   it roughly doubled the wall time of large legitimate fan-outs.
9. **You can only refund what you can identify.** Graceful stops produce a record of discarded
   work; hard kills don't.

## Limitations

- Agents are scripted, not real models. Real agents vary step to step in ways these families
  only approximate.
- The same author wrote the guardrails and every scenario family, including the adversarial
  ones. Held-out seeds reduce, but do not remove, that bias.
- Thresholds and prices are illustrative. Production use needs calibration against real
  traffic.
- One-hour horizon. Slow leaks are under-represented by design of the horizon.
- Unguarded recursive spawning is cut off by a simulator cap (3,000 agents in the fixed
  benchmark, 2,000 in the randomized suite); real spend would keep growing.
- Billing policies are computed from the simulation's records, not a real invoicing system.

## Using the guardrail layer elsewhere

`Layered` (`controllers.py`) and its building blocks (`Ledger`, `SpendWindow`,
`NoveltyTracker`, `CircuitBreaker`, `StopToken`) have no dependency on the simulator.
The hooks a real agent loop would call:

| Hook | When |
|---|---|
| `before_step(run, step, now)` | before each model call: proceed (with a reservation), throttle, or stop |
| `after_model(run, step, cost, decision, now)` | after the model call: settles the reservation, records signals |
| `tool_allowed` / `on_tool_result` | around each tool call |
| `before_commit(run, now)` | before committing a staged side effect |

To add a scenario, write a generator of `Step`s (see `scenarios.py` or `variants.py`). To add
a strategy, subclass `Controller` and register it in `bench.py` and `robustness.py`.

## Layout

```
agentguard/
  pricing.py      money in integer micro-dollars, illustrative prices and latency
  ledger.py       hierarchical budgets with reservations
  velocity.py     spend windows and action-novelty tracking
  breaker.py      circuit breaker
  stop.py         graceful vs hard stop
  sim.py          discrete-event simulator and controller interface
  controllers.py  none, monthly_alert, static_token_cap, layered (v1, v2, v3, combined, ceiling-only configs)
  scenarios.py    fixed scenarios: 3 legitimate + 3 runaway
  variants.py     13 randomized families, 7 of them adversarial
  bench.py        fixed benchmark, v1 ablation, billing report
  robustness.py   randomized suite and sensitivity sweep
  capsweep.py     v2 plus a token cap at several levels
  ceilingsweep.py dollar ceiling per run tree, no detectors
  replay.py       real agent runs (tau-bench, Aider) through the detectors
  live.py         live test: real model, planted faults, real ledger and detectors
  overhead.py     ledger microbenchmark
  verify_claims.py checks the article's numbers against results/
tests/
results/
```

## License

MIT
