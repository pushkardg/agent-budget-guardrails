# Hierarchical dollar ceiling only (no detectors) vs v2, seeds 2000-2029

Legitimate: % completed. Runaways: % contained (median runaway spend). 'Contained' needs the guardrail to stop it before the horizon and before the simulator's 2,000-agent safety cap, so a $100 ceiling on recursion can spend ~$100 and still count as not contained.

| Family | ceiling_25 | ceiling_50 | ceiling_100 | layered_v2 |
|---|---|---|---|---|
| normal_var | 100% | 100% | 100% | 100% |
| long_var | 87% | 100% | 100% | 100% |
| batch_var | 60% | 97% | 100% | 100% |
| wide_batch | 70% | 100% | 100% | 100% |
| polling | 100% | 100% | 100% | 100% |
| deep_delegation | 67% | 87% | 100% | 0% |
| retry_var | 100% ($24.39) | 100% ($49.36) | 100% ($99.37) | 100% ($0.65) |
| retry_varying | 100% ($24.39) | 100% ($49.36) | 100% ($99.37) | 100% ($0.65) |
| recursive_var | 100% ($24.86) | 100% ($49.86) | 50% ($99.86) | 100% ($4.86) |
| cycle_var | 100% ($24.53) | 100% ($49.53) | 100% ($99.54) | 100% ($1.97) |
| long_cycle | 100% ($24.50) | 100% ($49.49) | 100% ($99.50) | 100% ($15.18) |
| slow_drip | 0% ($5.32) | 0% ($5.32) | 0% ($5.32) | 0% ($5.32) |
| stuck_poll | 0% ($2.15) | 0% ($2.15) | 0% ($2.15) | 0% ($2.15) |
