# Replay of real agent runs (tau-bench historical trajectories)

1980 runs (1183 successful, 797 failed): Claude 3.5 Sonnet airline 400, Claude 3.5 Sonnet retail 920, GPT-4o airline 200, GPT-4o retail 460.

| Detector | Fired on successful runs | Fired on failed runs |
|---|---|---|
| exact (tool + arguments) | 0.0% (0) | 0.0% (0) |
| tool name only | 1.4% (16) | 2.0% (16) |
| tool name only, all messages alike | 20.4% (241) | 38.6% (308) |
| exact, tighter window (10/5) | 0.0% (0) | 0.0% (0) |
| breaker | 0.0% (0) | 0.0% (0) |

Exact = tool name plus arguments (the simulator's fingerprint). Tool name only = ignores arguments, a crude stand-in for matching by meaning; messages to the user are still compared by text. 'All messages alike' also treats every message to the user as one repeated action. Breaker = run-level circuit-breaker rule (5 failures of one tool, then 3 rejected calls), assuming 3 s per step.

## Run shape

- runs: 1980
- successful: 1183
- failed: 797
- median actions: 13.0
- max actions: 30
- median tool calls: 7.0
- pct runs with 10plus actions: 80.7
- runs with any tool error: 237
- failed runs with 3plus identical calls in a row: 0
- successful runs with 3plus identical calls in a row: 0
- max identical calls in a row: 2
- median est cost usd: 0.121
- max est cost usd: 0.691
- runs over 5 usd: 0

Replay is open-loop: it shows where a detector would have fired, not what the agent would have done next. These runs are short, so this tests false alarms on legitimate work, not detection of long real loops.
