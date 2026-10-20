# Robustness: 30 randomized seeds per family (seeds 1000-1029), 60-minute horizon

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
| long_var | static_token_cap | 7 | 1.8-21.3 | 28 | 0.0 |
| long_var | layered_v1 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | layered_v2 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | layered_v3 | 100 | 88.6-100.0 | 0 | 0.0 |
| long_var | v2_plus_cap | 7 | 1.8-21.3 | 0 | 0.0 |
| batch_var | none | 100 | 88.6-100.0 | 0 | 0.0 |
| batch_var | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| batch_var | static_token_cap | 97 | 83.3-99.4 | 4 | 0.0 |
| batch_var | layered_v1 | 100 | 88.6-100.0 | 0 | 18.3 |
| batch_var | layered_v2 | 100 | 88.6-100.0 | 0 | 18.3 |
| batch_var | layered_v3 | 100 | 88.6-100.0 | 0 | 18.3 |
| batch_var | v2_plus_cap | 100 | 88.6-100.0 | 0 | 18.3 |
| wide_batch* | none | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | monthly_alert | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | static_token_cap | 100 | 88.6-100.0 | 0 | 0.0 |
| wide_batch* | layered_v1 | 0 | 0.0-11.4 | 0 |  |
| wide_batch* | layered_v2 | 100 | 88.6-100.0 | 0 | 96.3 |
| wide_batch* | layered_v3 | 100 | 88.6-100.0 | 0 | 96.3 |
| wide_batch* | v2_plus_cap | 100 | 88.6-100.0 | 0 | 96.3 |
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
| deep_delegation** | layered_v1 | 57 | 39.2-72.6 | 0 | 18.7 |
| deep_delegation** | layered_v2 | 0 | 0.0-11.4 | 0 |  |
| deep_delegation** | layered_v3 | 100 | 88.6-100.0 | 0 | 32.2 |
| deep_delegation** | v2_plus_cap | 0 | 0.0-11.4 | 0 |  |

## Runaway workloads

| Family | Guardrail | Contained % | 95% CI | Median runaway $ | p95 runaway $ | Median time to contain (s) | Orphaned writes |
|---|---|---|---|---|---|---|---|
| retry_var | none | 0 | 0.0-11.4 | 198.92 | 202.01 |  | 0 |
| retry_var | monthly_alert | 0 | 0.0-11.4 | 198.92 | 202.01 |  | 0 |
| retry_var | static_token_cap | 100 | 88.6-100.0 | 5.94 | 6.26 | 204 | 0 |
| retry_var | layered_v1 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_var | layered_v2 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_var | layered_v3 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_var | v2_plus_cap | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_varying* | none | 0 | 0.0-11.4 | 198.92 | 202.01 |  | 0 |
| retry_varying* | monthly_alert | 0 | 0.0-11.4 | 198.92 | 202.01 |  | 0 |
| retry_varying* | static_token_cap | 100 | 88.6-100.0 | 5.94 | 6.26 | 204 | 0 |
| retry_varying* | layered_v1 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_varying* | layered_v2 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_varying* | layered_v3 | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| retry_varying* | v2_plus_cap | 100 | 88.6-100.0 | 0.67 | 1.18 | 42 | 0 |
| recursive_var | none | 0 | 0.0-11.4 | 285.15 | 399.4 |  | 0 |
| recursive_var | monthly_alert | 0 | 0.0-11.4 | 285.15 | 399.4 |  | 0 |
| recursive_var | static_token_cap | 0 | 0.0-11.4 | 285.15 | 399.4 |  | 0 |
| recursive_var | layered_v1 | 100 | 88.6-100.0 | 4.87 | 4.91 | 17 | 0 |
| recursive_var | layered_v2 | 100 | 88.6-100.0 | 4.87 | 4.91 | 17 | 0 |
| recursive_var | layered_v3 | 100 | 88.6-100.0 | 19.87 | 19.92 | 142 | 0 |
| recursive_var | v2_plus_cap | 100 | 88.6-100.0 | 4.87 | 4.91 | 17 | 0 |
| cycle_var | none | 0 | 0.0-11.4 | 148.88 | 153.63 |  | 0 |
| cycle_var | monthly_alert | 0 | 0.0-11.4 | 148.88 | 153.63 |  | 0 |
| cycle_var | static_token_cap | 100 | 88.6-100.0 | 6.07 | 6.33 | 276 | 21 |
| cycle_var | layered_v1 | 90 | 74.4-96.5 | 2.24 | 113.87 | 133 | 0 |
| cycle_var | layered_v2 | 100 | 88.6-100.0 | 2.24 | 8.83 | 137 | 0 |
| cycle_var | layered_v3 | 100 | 88.6-100.0 | 2.24 | 8.83 | 137 | 0 |
| cycle_var | v2_plus_cap | 100 | 88.6-100.0 | 2.24 | 6.09 | 137 | 0 |
| long_cycle* | none | 0 | 0.0-11.4 | 153.1 | 156.94 |  | 0 |
| long_cycle* | monthly_alert | 0 | 0.0-11.4 | 153.1 | 156.94 |  | 0 |
| long_cycle* | static_token_cap | 100 | 88.6-100.0 | 6.07 | 6.33 | 266 | 11 |
| long_cycle* | layered_v1 | 0 | 0.0-11.4 | 113.76 | 115.54 |  | 0 |
| long_cycle* | layered_v2 | 100 | 88.6-100.0 | 16.75 | 24.75 | 585 | 0 |
| long_cycle* | layered_v3 | 100 | 88.6-100.0 | 16.75 | 24.75 | 585 | 0 |
| long_cycle* | v2_plus_cap | 100 | 88.6-100.0 | 6.07 | 6.33 | 266 | 0 |
| slow_drip* | none | 0 | 0.0-11.4 | 5.3 | 6.41 |  | 0 |
| slow_drip* | monthly_alert | 0 | 0.0-11.4 | 5.3 | 6.41 |  | 0 |
| slow_drip* | static_token_cap | 3 | 0.6-16.7 | 5.3 | 6.41 | 3487 | 0 |
| slow_drip* | layered_v1 | 0 | 0.0-11.4 | 5.3 | 6.41 |  | 0 |
| slow_drip* | layered_v2 | 0 | 0.0-11.4 | 5.3 | 6.41 |  | 0 |
| slow_drip* | layered_v3 | 0 | 0.0-11.4 | 5.3 | 6.41 |  | 0 |
| slow_drip* | v2_plus_cap | 3 | 0.6-16.7 | 5.3 | 6.41 | 3487 | 0 |
| stuck_poll** | none | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
| stuck_poll** | monthly_alert | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
| stuck_poll** | static_token_cap | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
| stuck_poll** | layered_v1 | 100 | 88.6-100.0 | 0.18 | 0.18 | 266 | 0 |
| stuck_poll** | layered_v2 | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
| stuck_poll** | layered_v3 | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
| stuck_poll** | v2_plus_cap | 0 | 0.0-11.4 | 2.16 | 2.2 |  | 0 |
