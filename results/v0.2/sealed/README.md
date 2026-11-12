# v0.2 sealed results

The matrix contains 54 agent attempts and 12 baseline runs on 6 cases. Each of the three routes ran every case three times. The verifier used 16 new meal seeds per case.

| Model or baseline | Valid designs | Safety passes | Mean score (%) | vs. constant (pp) |
|---|---:|---:|---:|---:|
| GPT-6.1 Sol | 18/18 | 18/18 | 73.11 | +23.63 |
| Responsive baseline | 6/6 | 6/6 | 58.03 | +8.55 |
| MiniMax-M3.1-Flash | 16/18 | 14/18 | 51.82 | +2.34 |
| Constant baseline | 6/6 | 6/6 | 49.48 | — |
| Kimi-K3.1-Pro | 18/18 | 14/18 | 44.23 | -5.25 |

The highest model score was 73.11% from GPT-6.1 Sol. Its matched difference from the constant baseline was +23.63 percentage points with a case-resampled 95% interval of [+9.04, +38.22]. The bootstrap keeps all repetitions of each sampled case together.

Among their 14 safe designs each, MiniMax averaged 66.62% TIR and Kimi averaged 56.86%.

The six salted case hashes were published before the first trial. [Preregistered commitments](https://github.com/ZJUZhiyuCai/gri-design-bench/blob/7e80fb6dae655153b73c04503da063294a2f9a78/contract/v0.2/sealed-manifest.json)

The development case differences between GPT and the constant baseline had a standard deviation of 10.37 points. The planning calculation gave 5 cases for the 10-point target half-width before applying the registered six-case strata and 12-case cap. This produced 6 sealed cases. The case-resampled intervals above use observed sealed scores.

The audit checked 573 token reservations and aggregated 9,216 native trajectories. It reran 6 selected designs with 864 trajectories and matched the saved scores.

The labels identify the Magpie routes. The development plan records public checkpoint revisions for Kimi and MiniMax. The served checkpoint, engine and quantization are unknown.

[Per-attempt JSON](attempts.json) · [Per-case CSV](cases.csv) · [Paired differences](paired.csv) · [Summary and audit](summary.json)

[Protocol](../../../docs/v02/PROTOCOL.md) · [Registered plan](../../../contract/v0.2/sealed-plan.json)
