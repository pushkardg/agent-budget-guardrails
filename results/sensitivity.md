# Sensitivity: layered_v2, one threshold varied at a time (seeds 1000-1029 x 13 families)

| Parameter | Value | Legit completed % | Runaway contained % | Mean runaway $ | Where it fails |
|---|---|---|---|---|---|
| novelty_floor | 0.2 | 83.3 | 71.4 | 5.31 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| novelty_floor | 0.3 | 83.3 | 71.4 | 5.05 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| novelty_floor | 0.4 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| novelty_floor | 0.5 | 83.3 | 71.4 | 4.57 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| novelty_floor | 0.6 | 83.3 | 71.4 | 4.51 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| long_novelty_window | 0 | 83.3 | 71.4 | 17.86 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| long_novelty_window | 50 | 83.3 | 71.4 | 10.49 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| long_novelty_window | 100 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| long_novelty_window | 200 | 83.3 | 71.4 | 6.49 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tree_depth | 2 | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tree_depth | 3 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tree_depth | 5 | 96.7 | 71.4 | 5.84 | slow_drip missed 30/30; deep_delegation killed 6/30; stuck_poll missed 30/30 |
| max_tree_depth | 8 | 100.0 | 71.4 | 6.84 | slow_drip missed 30/30; stuck_poll missed 30/30 |
| run_budget_usd | 1.0 | 72.2 | 71.4 | 4.22 | long_var killed 1/30; batch_var killed 9/30; wide_batch killed 10/30; slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| run_budget_usd | 5.0 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| run_budget_usd | 20.0 | 93.9 | 71.4 | 6.86 | slow_drip missed 30/30; deep_delegation killed 11/30; stuck_poll missed 30/30 |
| max_run_budget_usd | 25.0 | 65.0 | 71.4 | 4.71 | long_var killed 6/30; batch_var killed 14/30; wide_batch killed 13/30; slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_run_budget_usd | 50.0 | 81.1 | 71.4 | 4.72 | batch_var killed 4/30; slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_run_budget_usd | 100.0 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_run_budget_usd | 200.0 | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tool_rejections | 1 | 83.3 | 71.4 | 4.66 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tool_rejections | 3 (default) | 83.3 | 71.4 | 4.72 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
| max_tool_rejections | 10 | 83.3 | 71.4 | 4.94 | slow_drip missed 30/30; deep_delegation killed 30/30; stuck_poll missed 30/30 |
