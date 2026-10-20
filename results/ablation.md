# Ablation: layered guardrails with one layer removed

| Scenario | Guardrail | Outcome | Total $ | Runaway $ | Time to contain | Wall time | Orphaned writes | Rolled-back writes | Notes |
|---|---|---|---|---|---|---|---|---|---|
| normal_task | layered (all layers) | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | - hierarchical budgets | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | - loop detection | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | - circuit breakers | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | - cap extensions | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| normal_task | - velocity throttling | completed | 0.51 | 0.00 |  | 90 s | 0 | 0 |  |
| long_task | layered (all layers) | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | - hierarchical budgets | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | - loop detection | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | - circuit breakers | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| long_task | - cap extensions | KILLED: budget exhausted for run0 subtree, extension denied | 4.88 | 0.00 |  | 9.2 min | 0 | 0 |  |
| long_task | - velocity throttling | completed | 19.80 | 0.00 |  | 37.5 min | 0 | 0 | 2 budget extension(s) |
| parallel_batch | layered (all layers) | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | - hierarchical budgets | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | - loop detection | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | - circuit breakers | completed | 39.70 | 0.00 |  | 8.4 min | 0 | 0 | 3 budget extension(s); throttled 9.0 min (summed across agents); 9 agents |
| parallel_batch | - cap extensions | KILLED: budget exhausted for run0 subtree, extension denied | 4.72 | 0.00 |  | 66 s | 0 | 6 | 9 agents |
| parallel_batch | - velocity throttling | completed | 39.70 | 0.00 |  | 7.1 min | 0 | 0 | 3 budget extension(s); 9 agents |
| tool_retry_loop | layered (all layers) | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | - hierarchical budgets | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | - loop detection | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | - circuit breakers | stopped: loop detected: action novelty 0.35 < 0.4 | 1.76 | 1.45 | 81 s | 2.5 min | 0 | 0 |  |
| tool_retry_loop | - cap extensions | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| tool_retry_loop | - velocity throttling | stopped: run breaker: agent kept calling a tool whose circuit is open | 1.00 | 0.68 | 42 s | 107 s | 0 | 0 |  |
| recursive_spawn | layered (all layers) | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | - hierarchical budgets | still spawning when simulator capped it at 3000 agents; then stopped: tenant budget exhausted (tenant:acme) | 199.94 | 199.87 | — | 39.4 min | 0 | 252 | throttled 1114 h (summed across agents); 3000 agents |
| recursive_spawn | - loop detection | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | - circuit breakers | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | - cap extensions | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| recursive_spawn | - velocity throttling | stopped: budget exhausted for run0 subtree, extension denied | 4.94 | 4.88 | 26 s | 52 s | 0 | 30 | 127 agents |
| nonconverging_plan | layered (all layers) | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | - hierarchical budgets | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | - loop detection | still running at horizon | 119.59 | 119.45 | — | 60.0 min | 0 | 0 | 5 budget extension(s); throttled 8.5 min (summed across agents) |
| nonconverging_plan | - circuit breakers | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | - cap extensions | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
| nonconverging_plan | - velocity throttling | stopped: loop detected: action novelty 0.35 < 0.4 | 2.23 | 2.09 | 2.7 min | 3.4 min | 0 | 0 |  |
