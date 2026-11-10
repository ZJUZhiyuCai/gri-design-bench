# Pilot leaderboard

One run per model/instance. Six development and six sealed cases in one task family. Safety gates were frozen before search. These are route-and-harness results, not authenticated upstream-model rankings. No significance claim.

| Split | Method / requested route | Valid | Feasible | Mean safe TIR (%) | Mean CPU (s) | API errors |
|---|---|---:|---:|---:|---:|---:|
| development | codex/gpt-6.1-sol | 6/6 | 6/6 | 68.64 | 24.13 | 0 |
| development | constant_grid | 6/6 | 6/6 | 59.83 | 29.78 | 0 |
| development | sobol | 6/6 | 6/6 | 56.51 | 29.78 | 0 |
| development | wanjie/deepseek-v4.1-flash-1017 | 6/6 | 5/6 | 51.26 | 27.30 | 0 |
| development | differential_evolution | 6/6 | 5/6 | 49.46 | 29.75 | 0 |
| development | tokendance/glm-5.3 | 6/6 | 5/6 | 45.03 | 8.59 | 9 |
| sealed | codex/gpt-6.1-sol | 6/6 | 6/6 | 75.06 | 26.81 | 0 |
| sealed | wanjie/deepseek-v4.1-flash-1017 | 6/6 | 6/6 | 73.02 | 28.73 | 0 |
| sealed | constant_grid | 6/6 | 5/6 | 58.26 | 29.77 | 0 |
| sealed | differential_evolution | 6/6 | 5/6 | 54.39 | 29.78 | 0 |
| sealed | tokendance/glm-5.3 | 6/6 | 5/6 | 44.99 | 9.58 | 5 |
| sealed | sobol | 6/6 | 5/6 | 44.93 | 29.75 | 0 |

`safe_tir` is mean TIR if every trajectory passes all safety gates, and zero otherwise. An infeasible design can have high raw TIR; that does not make it safe. Aggregates include every attempted case. Native solver errors, missing files, API errors, and infrastructure errors are retained in per-trial records.

The JSON/CSV tables also contain raw TIR (valid trajectories only), wall time, prompt/completion tokens, and infrastructure errors. Actual billing is unavailable. Baseline and agent CPU caps are identical. Provider-default inference effort may differ.

Development designs, code, transcripts and native traces are open in the per-trial directories. Sealed case details and transcripts remain private; their hashes are included. The full private suite cannot be reproduced from this public repository alone.
