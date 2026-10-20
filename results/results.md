# Benchmark results (horizon 60 min, simulated)

| Scenario | Guardrail | Outcome | Total $ | Runaway $ | Time to contain | Wall time | Orphaned writes | Rolled-back writes | Notes |
|---|---|---|---|---|---|---|---|---|---|
| normal_task | none | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | monthly_alert | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | static_token_cap | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | layered_v1 | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | layered_v2 | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | layered_v3 | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | v2_plus_cap | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| long_task | none | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 |  |
| long_task | monthly_alert | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 |  |
| long_task | static_token_cap | KILLED: token cap 2,000,000 exceeded (watchdog kill) | 6.53 | 0.00 |  | 12.4 min | 1 | 0 |  |
| long_task | layered_v1 | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | layered_v2 | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | layered_v3 | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | v2_plus_cap | KILLED: token cap 2,000,000 exceeded (graceful) | 6.53 | 0.00 |  | 12.4 min | 0 | 0 | 1 budget extension(s) |
| parallel_batch | none | completed | 39.70 | 0.00 |  | 7.1 min | 0 | 0 | 9 agents |
| parallel_batch | monthly_alert | completed | 39.70 | 0.00 |  | 7.1 min | 0 | 0 | 9 agents |
| parallel_batch | static_token_cap | completed | 39.70 | 0.00 |  | 7.1 min | 0 | 0 | 9 agents |
| parallel_batch | layered_v1 | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | layered_v2 | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | layered_v3 | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | v2_plus_cap | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| tool_retry_loop | none | still running at horizon | 199.33 | 199.02 | — | 60.0 min | 0 | 0 |  |
| tool_retry_loop | monthly_alert | still running at horizon | 199.33 | 199.02 | — | 60.0 min | 0 | 0 | alert at 79 min |
| tool_retry_loop | static_token_cap | stopped: token cap 2,000,000 exceeded (watchdog kill) | 6.41 | 6.10 | 3.6 min | 4.8 min | 0 | 0 |  |
| tool_retry_loop | layered_v1 | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | layered_v2 | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | layered_v3 | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | v2_plus_cap | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| recursive_spawn | none | still spawning when simulator capped it at 3000 agents | 427.60 | 427.53 | — | 101 s | 0 | 0 | 3000 agents |
| recursive_spawn | monthly_alert | still spawning when simulator capped it at 3000 agents | 427.60 | 427.53 | — | 101 s | 0 | 0 | alert at 31 min; 3000 agents |
| recursive_spawn | static_token_cap | still spawning when simulator capped it at 3000 agents | 427.60 | 427.53 | — | 101 s | 0 | 0 | 3000 agents |
| recursive_spawn | layered_v1 | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | layered_v2 | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | layered_v3 | stopped: budget exhausted for run0 subtree, extension denied | 19.93 | 19.87 | 2.6 min | 3.0 min | 0 | 56 | 7 budget extension(s); throttled 8 h (summed across agents); 413 agents |
| recursive_spawn | v2_plus_cap | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| nonconverging_plan | none | still running at horizon | 140.94 | 140.81 | — | 60.0 min | 0 | 0 |  |
| nonconverging_plan | monthly_alert | still running at horizon | 140.94 | 140.81 | — | 60.0 min | 0 | 0 |  |
| nonconverging_plan | static_token_cap | stopped: token cap 2,000,000 exceeded (watchdog kill) | 6.40 | 6.26 | 5.2 min | 6.0 min | 1 | 0 |  |
| nonconverging_plan | layered_v1 | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | layered_v2 | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | layered_v3 | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | v2_plus_cap | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
