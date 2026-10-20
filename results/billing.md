# What the customer is charged, under three billing policies

Provider cost is always the full spend. The policies differ in who absorbs it.

| Scenario | Guardrail | Provider cost $ | Bill everything $ | Don't bill rolled-back work $ | Absorb guardrail-stopped runs $ |
|---|---|---|---|---|---|
| long_task | static_token_cap | 6.53 | 6.53 | 6.53 | 0.00 |
| long_task | v2_plus_cap | 6.53 | 6.53 | 6.53 | 0.00 |
| tool_retry_loop | none | 199.33 | 199.33 | 199.33 | 199.33 |
| tool_retry_loop | monthly_alert | 199.33 | 199.33 | 199.33 | 199.33 |
| tool_retry_loop | static_token_cap | 6.41 | 6.41 | 6.41 | 0.00 |
| tool_retry_loop | layered_v1 | 1.00 | 1.00 | 1.00 | 0.00 |
| tool_retry_loop | layered_v2 | 1.00 | 1.00 | 1.00 | 0.00 |
| tool_retry_loop | layered_v3 | 1.00 | 1.00 | 1.00 | 0.00 |
| tool_retry_loop | v2_plus_cap | 1.00 | 1.00 | 1.00 | 0.00 |
| recursive_spawn | none | 427.60 | 427.60 | 427.60 | 427.60 |
| recursive_spawn | monthly_alert | 427.60 | 427.60 | 427.60 | 427.60 |
| recursive_spawn | static_token_cap | 427.60 | 427.60 | 427.60 | 427.60 |
| recursive_spawn | layered_v1 | 4.94 | 4.94 | 4.09 | 0.24 |
| recursive_spawn | layered_v2 | 4.94 | 4.94 | 4.09 | 0.24 |
| recursive_spawn | layered_v3 | 19.93 | 19.93 | 18.34 | 5.80 |
| recursive_spawn | v2_plus_cap | 4.94 | 4.94 | 4.09 | 0.24 |
| nonconverging_plan | none | 140.94 | 140.94 | 140.94 | 140.94 |
| nonconverging_plan | monthly_alert | 140.94 | 140.94 | 140.94 | 140.94 |
| nonconverging_plan | static_token_cap | 6.40 | 6.40 | 6.40 | 0.00 |
| nonconverging_plan | layered_v1 | 2.23 | 2.23 | 2.23 | 0.00 |
| nonconverging_plan | layered_v2 | 2.23 | 2.23 | 2.23 | 0.00 |
| nonconverging_plan | layered_v3 | 2.23 | 2.23 | 2.23 | 0.00 |
| nonconverging_plan | v2_plus_cap | 2.23 | 2.23 | 2.23 | 0.00 |
