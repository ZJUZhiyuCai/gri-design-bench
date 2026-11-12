# v0.2 development results

The matrix contains 54 agent attempts and 12 baseline runs on 6 cases. Each of the three routes ran every case three times. The verifier used 16 new meal seeds per case.

| Model or baseline | Valid designs | Safety passes | Mean score (%) | vs. constant (pp) |
|---|---:|---:|---:|---:|
| Constant baseline | 6/6 | 6/6 | 46.97 | — |
| GPT-6.1 Sol | 18/18 | 12/18 | 45.90 | -1.07 |
| Responsive baseline | 6/6 | 5/6 | 41.44 | -5.53 |
| Kimi-K3.1-Pro | 18/18 | 14/18 | 41.14 | -5.83 |
| MiniMax-M3.1-Flash | 15/18 | 7/18 | 22.46 | -24.51 |

The highest model score was 45.90% from GPT-6.1 Sol. Its matched difference from the constant baseline was -1.07 percentage points with a case-resampled 95% interval of [-8.43, +6.50]. The bootstrap keeps all repetitions of each sampled case together.

| Model | vs. old prompt example (pp) | vs. refined long-budget reference (pp) |
|---|---:|---:|
| GPT-6.1 Sol | +31.48 | -23.86 |
| Kimi-K3.1-Pro | +26.72 | -28.62 |
| MiniMax-M3.1-Flash | +8.04 | -47.30 |

MiniMax produced 15/18 legal submissions, compared with 6/18 on the same development cases under v0.1.1. The v0.2 runner retained a design in 2 attempts that later received a truncated response. The new submission interface and reasoning request both changed for this pilot.

The audit checked 579 token reservations and aggregated 9,072 native trajectories. It reran 5 selected designs with 720 trajectories and matched the saved scores.

[Per-attempt JSON](attempts.json) · [Per-case CSV](cases.csv) · [Paired differences](paired.csv) · [Summary and audit](summary.json)

[Protocol](../../../docs/v02/PROTOCOL.md) · [Registered plan](../../../contract/v0.2/development-plan.json)
