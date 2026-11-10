# Shared responsive formulation

The submitted formulation uses the same six coefficients for all three adolescent profiles. Amplitude and finite reservoir load scale only with the provided native TDI. The minimum permitted relative leak provides the strongest available glucose dependence. A short filter time avoids adding substantial delay to the existing physiological insulin delay. The maximum permitted reservoir load reduces premature exhaustion.

Search used the public physiology with RK4 at one-minute steps, then validation used the API default quarter-minute steps. A seeded stochastic search varied amplitude, EC50 and Hill exponent on three meal seeds, each with all three challenges. Its objective penalized low glucose and retained only candidates with no time below 70 and full-horizon minima at least 73 mg/dL. The search log records every candidate. Validation then used four additional meal seeds, all three challenges and all three patients, reducing amplitude if needed to seek a 75 mg/dL minimum margin.

Selected design:
```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.00034818221131947087,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 86.63402319711737,
    "hill_n": 8.126497029348522,
    "tau_min": 0.05,
    "theta_L": 4.0
  }
}
```

Additional-seed validation results:
```json
{
  "mean_tir": 73.80497685185185,
  "max_trajectory_tbr70": 0.0,
  "max_trajectory_tbr54": 0.0,
  "minimum_glucose": 75.48287903069702,
  "trajectories": 36,
  "feasible": true,
  "safe_tir": 73.80497685185185
}
```

These are simulation estimates from public RK4 physiology, not independent native-dopri5 verification. No claim is made that training or validation safety guarantees heldout safety. Additional meals can produce different outcomes, and any heldout threshold violation makes the benchmark score zero.

Reproduction: set PYTHONPATH=/opt and run `python /work/output/search.py initial`, then `search`, then `validate`. Search uses random seed 1047 and a 15.5 CPU-second stopping budget, so the exact final iteration count depends on hardware; stored histories preserve the actual evaluated designs and metrics.

The validation trajectory with the lowest minimum was also checked with the native dopri5 solver:
```json
{
  "patient": "adolescent#002",
  "seed": 718111,
  "variant": "large_dinner",
  "metrics": {
    "tir": 60.416666666666664,
    "tbr70": 0.0,
    "tbr54": 0.0,
    "minimum": 75.48287906838777,
    "mean_glucose": 172.08702631230173
  }
}
```
This is a single native cross-check; the other reported validation trajectories use RK4.
