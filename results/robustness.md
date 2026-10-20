# Robustness: 30 randomized seeds per family (seeds 2000-2029), 60-minute horizon

Families marked * were written to defeat layered_v1; ** were written afterwards to defeat layered_v2.
95% CI = Wilson score interval on n runs: 30/30 means the true rate is very likely above ~89%, not that it is 100%.

## Legitimate workloads

| Family | Guardrail | Completed % | 95% CI | Orphaned writes | Median slowdown vs none % |
|---|---|---|---|---|---|
| normal_var | none | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | static_token_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | layered_v1 | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | layered_v2 | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | layered_v3 | 100 | 88.6-100.0 | 0 | 0.0 |
| normal_var | v2_plus_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | none | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | static_token_cap | 0 | 0.0-11.4 | 30 |  |
| long_var | layered_v1 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | layered_v2 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | layered_v3 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | v2_plus_cap | 0 | 0.0-11.4 | 0 |  |
| batch_var | none | 100 | 88.6-100.0 | 0 | 0.0 |
| batch_var | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| batch_var | static_token_cap | 97 | 83.3-99.4 | 2 | 0.0 |
| batch_var | layered_v1 | 100 | 88.6-100.0 | 0 | 9.6 |
| batch_var | layered_v2 | 100 | 88.6-100.0 | 0 | 9.6 |
| batch_var | layered_v3 | 100 | 88.6-100.0 | 0 | 9.6 |
| batch_var | v2_plus_cap | 97 | 83.3-99.4 | 0 | 11.4 |
| wide_batch* | none | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | static_token_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | layered_v1 | 0 | 0.0-11.4 | 0 |  |
| wide_batch* | layered_v2 | 100 | 88.6-100.0 | 0 | 99.4 |
| wide_batch* | layered_v3 | 100 | 88.6-100.0 | 0 | 99.4 |
| wide_batch* | v2_plus_cap | 100 | 88.6-100.0 | 0 | 99.4 |
| polling* | none | 100 | 88.6-100.0 | 0 | 0.0 |
| polling* | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| polling* | static_token_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| polling* | layered_v1 | 0 | 0.0-11.4 | 0 |  |
| polling* | layered_v2 | 100 | 88.6-100.0 | 0 | 0.0 |
| polling* | layered_v3 | 100 | 88.6-100.0 | 0 | 0.0 |
| polling* | v2_plus_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| deep_delegation** | none | 100 | 88.6-100.0 | 0 | 0.0 |
| deep_delegation** | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| deep_delegation** | static_token_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| deep_delegation** | layered_v1 | 50 | 33.2-66.8 | 0 | 0.0 |
| deep_delegation** | layered_v2 | 0 | 0.0-11.4 | 0 |  |
| deep_delegation** | layered_v3 | 100 | 88.6-100.0 | 0 | 40.5 |
| deep_delegation** | v2_plus_cap | 0 | 0.0-11.4 | 0 |  |

## Runaway workloads

| Family | Guardrail | Contained % | 95% CI | Median runaway $ | p95 runaway $ | Median time to contain (s) | Orphaned writes |
|---|---|---|---|---|---|---|---|
| retry_var | none | 0 | 0.0-11.4 | 198.89 | 202.82 |  | 0 |
| retry_var | monthly_alert | 0 | 0.0-11.4 | 198.89 | 202.82 |  | 0 |
| retry_var | static_token_cap | 100 | 88.6-100.0 | 5.99 | 6.28 | 210 | 0 |
| retry_var | layered_v1 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_var | layered_v2 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_var | layered_v3 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_var | v2_plus_cap | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_varying* | none | 0 | 0.0-11.4 | 198.89 | 202.82 |  | 0 |
| retry_varying* | monthly_alert | 0 | 0.0-11.4 | 198.89 | 202.82 |  | 0 |
| retry_varying* | static_token_cap | 100 | 88.6-100.0 | 5.99 | 6.28 | 210 | 0 |
| retry_varying* | layered_v1 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_varying* | layered_v2 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_varying* | layered_v3 | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| retry_varying* | v2_plus_cap | 100 | 88.6-100.0 | 0.65 | 0.97 | 42 | 0 |
| recursive_var | none | 0 | 0.0-11.4 | 341.77 | 399.24 |  | 0 |
| recursive_var | monthly_alert | 0 | 0.0-11.4 | 341.77 | 399.24 |  | 0 |
| recursive_var | static_token_cap | 0 | 0.0-11.4 | 341.77 | 399.24 |  | 0 |
| recursive_var | layered_v1 | 100 | 88.6-100.0 | 4.86 | 4.91 | 26 | 0 |
| recursive_var | layered_v2 | 100 | 88.6-100.0 | 4.86 | 4.91 | 26 | 0 |
| recursive_var | layered_v3 | 100 | 88.6-100.0 | 19.85 | 19.92 | 152 | 0 |
| recursive_var | v2_plus_cap | 100 | 88.6-100.0 | 4.86 | 4.91 | 26 | 0 |
| cycle_var | none | 0 | 0.0-11.4 | 144.5 | 152.96 |  | 0 |
| cycle_var | monthly_alert | 0 | 0.0-11.4 | 144.5 | 152.96 |  | 0 |
| cycle_var | static_token_cap | 100 | 88.6-100.0 | 6.13 | 6.33 | 281 | 25 |
| cycle_var | layered_v1 | 87 | 70.3-94.7 | 1.97 | 114.66 | 134 | 0 |
| cycle_var | layered_v2 | 100 | 88.6-100.0 | 1.97 | 10.02 | 135 | 0 |
| cycle_var | layered_v3 | 100 | 88.6-100.0 | 1.97 | 10.02 | 135 | 0 |
| cycle_var | v2_plus_cap | 100 | 88.6-100.0 | 1.97 | 6.21 | 135 | 0 |
| long_cycle* | none | 0 | 0.0-11.4 | 152.8 | 156.65 |  | 0 |
| long_cycle* | monthly_alert | 0 | 0.0-11.4 | 152.8 | 156.65 |  | 0 |
| long_cycle* | static_token_cap | 100 | 88.6-100.0 | 6.11 | 6.33 | 269 | 14 |
| long_cycle* | layered_v1 | 0 | 0.0-11.4 | 114.02 | 115.57 |  | 0 |
| long_cycle* | layered_v2 | 100 | 88.6-100.0 | 15.18 | 22.12 | 526 | 0 |
| long_cycle* | layered_v3 | 100 | 88.6-100.0 | 15.18 | 22.12 | 526 | 0 |
| long_cycle* | v2_plus_cap | 100 | 88.6-100.0 | 6.11 | 6.33 | 269 | 0 |
| slow_drip* | none | 0 | 0.0-11.4 | 5.32 | 6.71 |  | 0 |
| slow_drip* | monthly_alert | 0 | 0.0-11.4 | 5.32 | 6.71 |  | 0 |
| slow_drip* | static_token_cap | 7 | 1.8-21.3 | 5.32 | 6.59 | 3525 | 0 |
| slow_drip* | layered_v1 | 0 | 0.0-11.4 | 5.32 | 6.71 |  | 0 |
| slow_drip* | layered_v2 | 0 | 0.0-11.4 | 5.32 | 6.71 |  | 0 |
| slow_drip* | layered_v3 | 0 | 0.0-11.4 | 5.32 | 6.71 |  | 0 |
| slow_drip* | v2_plus_cap | 7 | 1.8-21.3 | 5.32 | 6.59 | 3525 | 0 |
| stuck_poll** | none | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
| stuck_poll** | monthly_alert | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
| stuck_poll** | static_token_cap | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
| stuck_poll** | layered_v1 | 100 | 88.6-100.0 | 0.18 | 0.18 | 266 | 0 |
| stuck_poll** | layered_v2 | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
| stuck_poll** | layered_v3 | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
| stuck_poll** | v2_plus_cap | 0 | 0.0-11.4 | 2.15 | 2.2 |  | 0 |
