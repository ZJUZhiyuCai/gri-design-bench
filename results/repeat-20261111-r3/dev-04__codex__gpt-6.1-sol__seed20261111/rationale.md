# Shared formulation for dev-04

The submitted design is responsive, with one coefficient vector shared by adult#004, adult#005, and adult#006. Only the benchmark's native TDI scaling changes amplitude and reservoir between patients.

```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.00113,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 380,
    "hill_n": 14,
    "tau_min": 0.05,
    "theta_L": 1.25
  }
}
```

## Selection and physical tradeoff

I compared constant infusion with responsive formulations using deterministic grids and a seeded random search. The search explored low and high response thresholds, multiple Hill slopes, and amplitudes. Screening used the public physiological equations with one-minute RK4 steps. The selected candidate was repeated with the public default quarter-minute RK4 integration.

The maximum allowed load, 1.25 times native TDI, provides the greatest available coverage. The minimum permitted leak allows the largest fractional change in release as glucose rises. A 380 mg/dL EC50 and Hill exponent 14 keep release close to its basal floor at lower glucose while increasing release during marked hyperglycemia. The 0.05-minute filter avoids additional response delay. No individualized fitted coefficients, meal boluses, or external controller are used.

The basal floor is 0.0005791212 times TDI per minute, and the maximum rate is 0.0017091212 times TDI per minute. The finite reservoir is enforced in every simulation. At this floor, even without glucose-driven increments, the reservoir cannot last the whole three days. Reservoir depletion and substantial late hyperglycemia remain material limitations. The objective is time in range under the supplied load constraint, not mean glucose or continuous three-day coverage.

## Validation evidence

All validation uses native RandomScenario meals, weight scaling, and ordinary, missed-lunch, and large-dinner variants. No physiology state carries over between candidates. TIR and TBR omit day one; minimum glucose includes the full horizon.

| Evaluation | Trajectories | Mean TIR | Maximum TBR70 | Maximum TBR54 | Full-horizon minimum |
|---|---:|---:|---:|---:|---:|
| 24 fresh seeds, quarter-minute RK4 | 216 | 27.11275% | 0.000% | 0.000% | 76.49763 mg/dL |
| 60 additional seeds, one-minute RK4 | 540 | 28.08083% | 0.000% | 0.000% | 71.82804 mg/dL |

The final 24-seed comparison rejected a seemingly strong alternative after it exceeded 4% TBR70 on a fresh scenario. Selection required minimum glucose at least 65 mg/dL, maximum TBR70 at most 1%, and zero TBR54 on that comparison, adding margins to the benchmark thresholds. The selected design actually had zero TBR70 across both validation sets.

The lowest-glucose trajectory in the separate 60-seed audit was also simulated with native simglucose dopri5: patient adult#006, seed 86746399, variant ordinary. Its native full-horizon minimum was 71.83007 mg/dL, with zero TBR70 and TBR54. This is one native trajectory check, not native verification of the entire cohort/scenario collection.

Observed safety on these seeds does not guarantee held-out safety. Meals in the final benchmark are new, and the trusted verifier independently recomputes all outcomes. The 24-seed set informed selection; the additional 60-seed audit did not change the selected design.

## Reproduction

Run `OPENBLAS_NUM_THREADS=1 PYTHONPATH=/opt python /work/output/search.py` in the supplied environment. The standalone script reproduces all decision-relevant search phases, seeds, screening criteria, atomic design checkpoints, and quarter-minute final validation. It starts a new results log. `results.jsonl` records the search. `validation.json` records the 24-seed final check. The supplementary `audit.py` reproduces the separate 60-seed and native checks, stored in `extra_validation.json` and `native_check.json`.

This is a simulation benchmark submission, not a clinical recommendation.
