# Replay of real coding-agent runs (Aider on SWE-bench Lite, May 2024)

300 runs: 79 resolved, 221 unresolved. 'Stuck' = the identical failing edit proposed 3+ times (16 runs, 5 of them later resolved).

| Detector | Fired on resolved (79) | Fired on unresolved (221) | Fired on stuck (16) |
|---|---|---|---|
| exact (tool + arguments) | 1 | 0 | 0 |
| exact, tighter window (10/5) | 1 | 2 | 0 |
| file name only | 20 | 98 | 14 |
| breaker as simulated (5 in 60 s), real timestamps | 0 | 1 | 1 |
| breaker, 5 in 30 min, real timestamps | 9 | 69 | 12 |
| breaker, 5 in 30 min, edits only | 3 | 11 | 5 |

Exact = edit file plus a hash of the proposed change. File name only = ignores the change. Breaker rows use each action's time interpolated between the transcript's session timestamps (297 runs with usable timestamps). The simulated breaker opens after 5 failures of one tool in 60 s.

## Run shape

- runs: 300
- resolved: 79
- unresolved: 221
- stuck: 16
- stuck resolved: 5
- median actions: 6.0
- max actions: 106
- stuck min actions: 7
- stuck max actions: 106
- edits: 3491
- failed edits: 779
- failed test rounds: 1142
- max identical calls in a row: 4
- runs with usable timestamps: 297
- median seconds per action between timestamps: 71.8

Aider's own limits (a few reflections per session, a few sessions per task) already bound these runs, so they can't contain unbounded runaways. Replay is open-loop.
