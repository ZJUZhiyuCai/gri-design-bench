# v0.2 calibration

The two-seed evaluation can miss an unsafe meal scenario. Five of the first 36 fixed designs passed some of the 64 diagnostic seeds and failed others. Within those five designs, drawing two of the 64 seeds would miss every violation 75.4% of the time on average. The corresponding frequencies are 54.0% for eight seeds, 38.5% for 16 and 21.2% for 32. These are exact probabilities for sampling from the diagnostic panel. We chose 16 independent seeds per development case for the native verifier.

The full study screened 27,648 trajectories and checked 981 selected trajectories with the native integrator. It observed 0 differences in safety classification on those checks. The fixed checkpoints and controls use 5,184 native trajectories on the public development panel. The refined reference adds 864 trajectories.

| Control | Safety passes /6 | Mean score (%) |
|---|---:|---:|
| Zero release | 6/6 | 0.00 |
| Old prompt example | 5/6 | 14.42 |
| Constant, 30 CPU s | 6/6 | 48.46 |
| Responsive, 30 CPU s | 5/6 | 45.93 |
| Responsive, 300 CPU s | 2/6 | 19.63 |
| Responsive, 3,000 CPU s | 2/6 | 19.65 |
| Responsive, refined on 16 training seeds | 6/6 | 69.76 |

The 30, 300 and 3,000 CPU second checkpoints advance the same optimizer on two training seeds. Each checkpoint is then scored on the separate evaluation panel. When the 300-second checkpoints were first evaluated, several high-scoring training designs exceeded the time-below-70 limit on fresh meals. The refinement step searches around all three checkpoints on a wider independent training panel, then evaluates the selected design natively. This yields the reference used in the pilot comparison. Competitive baselines run inside the agent sandbox under its CPU limit.

In the earlier 324-attempt comparison, 113 attempts did not reach physiological scoring. Ten had a design file present while an auxiliary file was missing or invalid. Forty-one had two recorded API errors. The API counts can overlap the file categories. For the earlier MiniMax development failures, the separate response audit confirmed nine empty visible responses at the 6,000-token request cap. A saved checkpoint in v0.2 survives a later truncated response.

[Checkpoint designs](checkpoints.json) · [CPU curve](cpu-curve.csv) · [64-seed study](scenarios.json) · [Native controls](native-controls.json) · [Refined designs](robust-reference.json) · [Audit summary](summary.json)
