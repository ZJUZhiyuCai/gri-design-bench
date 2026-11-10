# Failure and resource accounting

All 36 formal model trials are included. Original development calibration is archived separately and is not pooled into these rows. Safety failure types can overlap within a trial.

| Route | Split | Complete native evaluations | Feasible | Submission failures | API error requests | Mean CPU (s) |
|---|---|---:|---:|---:|---:|---:|
| codex/gpt-6.1-sol | development | 6/6 | 6/6 | 0 | 0 | 24.13 |
| codex/gpt-6.1-sol | sealed | 6/6 | 6/6 | 0 | 0 | 26.81 |
| tokendance/glm-5.3 | development | 6/6 | 5/6 | 0 | 9 | 8.59 |
| tokendance/glm-5.3 | sealed | 6/6 | 5/6 | 0 | 5 | 9.58 |
| wanjie/deepseek-v4.1-flash-1017 | development | 6/6 | 5/6 | 0 | 0 | 27.30 |
| wanjie/deepseek-v4.1-flash-1017 | sealed | 6/6 | 6/6 | 0 | 0 | 28.73 |

See the JSON for token totals, reported reasoning-token counts, call counts and safety-failure categories. Failed API requests consume calls and wall time; their token usage and cost are unavailable. Reported token totals therefore do not establish a strict cap on all upstream inference. These observations describe the configured routes and harness. They do not isolate upstream model reasoning ability or establish statistically significant differences.
