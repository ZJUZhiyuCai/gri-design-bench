# Shared responsive formulation for dev-02

The final design uses one coefficient set for all three known adolescent profiles. Amplitude and reservoir load scale only with native TDI, as required.

```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.0003622222222222222,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 90.0,
    "hill_n": 20.0,
    "tau_min": 0.05,
    "theta_L": 4.0
  }
}
```

Minimum permitted relative leak provides the greatest available reduction in release at low glucose. The steep response near 90 mg/dL reduces delivery as glucose falls; rapid filtering avoids additional material delay. Insulin absorption and action still have physiological delays. The maximum permitted reservoir (4 times TDI) avoids premature exhaustion during the three-day experiment.

Search used unchanged public physiology with RK4 at one-minute steps, followed by checks at the API-default quarter-minute steps. Differential evolution (288 candidates, deterministic seed 19427) used the supplied seed and two additional seeds, with all three variants. A 120-candidate grid extended the search toward lower EC50. Six finalists were evaluated on 16 different seeds; the selected shape then underwent a local dose sweep. Selection penalized hypoglycemia and required minimum glucose at least 65 mg/dL with zero TBR70 in the 16-seed bank. A final bank of 32 additional seeds tested all patients and variants (288 trajectories). The worst fresh seed and variant received a quarter-minute integration cross-check for all patients.

Observed results:

| Bank | Trajectories | Mean TIR (%) | Worst TBR70 (%) | Worst TBR54 (%) | Full-horizon minimum (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Supplied training seed, quarter-minute RK4 | 9 | 84.2477 | 0.0000 | 0.0000 | 71.3162 |
| 16-seed selection bank, quarter-minute RK4 | 144 | 76.1386 | 0.0000 | 0.0000 | 71.1768 |
| 32 fresh seeds, one-minute RK4 | 288 | 75.6934 | 0.0000 | 0.0000 | 71.1774 |
| Worst fresh seed/variant, quarter-minute RK4 | 3 | 68.7500 | 0.0000 | 0.0000 | 71.1774 |

TIR/TBR omit day one; minimum glucose includes all three days and all minute endpoints. These are public fast-integrator observations, not results from the trusted native dopri5 verifier. Unobserved meal seeds can still violate safety constraints; sampled feasibility is not a held-out safety guarantee. This is a simulation benchmark formulation, not a clinical recommendation.

Reproduction: run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`. The combined script repeats coarse search, grid refinement, validation, local dose tuning, and atomic final design saving. Detailed observed trajectories and seed banks are stored in final_verification.json.
