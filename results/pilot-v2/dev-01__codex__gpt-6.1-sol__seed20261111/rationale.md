# Shared responsive formulation for dev-01

The submitted formulation uses one set of coefficients for adult#001, adult#002, and adult#003. Native TDI is used only for the benchmark-defined amplitude and reservoir scaling. No patient-specific coefficient fitting, meal boluses, external insulin, or additional controller is used.

## Final parameters

```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.000479264769866338,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 83.90872981592558,
    "hill_n": 8.737603720345396,
    "tau_min": 11.425169064546777,
    "theta_L": 4.0
  }
}
```

The minimum permitted relative leak preserves the largest available ratio between release at high and low glucose. The selected Hill curve transitions near 83.91 mg/dL with exponent 8.74; its amplitude limits high-glucose delivery while reducing release as glucose falls. Filtering uses 11.43 minutes. The maximum permitted load, 4 TDI, reduces the risk that reservoir exhaustion interrupts treatment during the three-day horizon. The formulation obeys every supplied parameter bound.

## Search and selection

The reproducible implementation is `search.py`. Running `python search.py all` repeats screening, three deterministic differential-evolution searches, and final validation. Running `python search.py validate` evaluates the saved design. The initial sweep screened six amplitudes. The first optimization used the provided meal seed and all three variants. Subsequent optimization used seeds 6111001, 82731, 492017, 951321, and 160021, with all variants and all patients. NumPy/SciPy differential evolution used fixed seeds 145, 214, and 914, a population multiplier of five, and respectively three, four, and two generations. The search fixed leak at its lower bound and load at its upper bound, while varying amplitude, EC50, Hill exponent, and filter time.

Screening used the public physiological equations with RK4 substeps of one minute, preserving the three-minute release updates and native one-minute meal handling. The score penalized worst-trajectory low-glucose exposure above 0.3% in the two later searches, and minima below 65 or 66 mg/dL. These margins deliberately exceed the safety requirements. Full search bounds and penalties are explicit in the code. Feasible incumbents were checkpointed atomically. The final saved formulation was selected before the independent 20-seed evaluation; no parameter was adjusted after that evaluation.

## Final verification

The final checks used the public API's standard RK4 step of 0.25 minute, on three-day trajectories. TIR and TBR omit day one; minima include all three days. These are fast-simulator results, not native dopri5 verifier results.

| Scenario set | Trajectories | Mean TIR 70–180 | Worst TBR70 | Worst TBR54 | Full-horizon minimum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Five optimization seeds | 45 | 83.7546% | 0% | 0% | 70.8179 mg/dL |
| Independent seeds 700001–700020 | 180 | 77.9045% | 0% | 0% | 70.8028 mg/dL |

For the original training seed alone, final mean TIR was 87.6042%. Every set includes ordinary meals, missed day-two lunch, and 50% larger day-two dinner. Full per-trajectory results are saved in `validation.json`. One-minute versus quarter-minute integration agreed to about 0.001 percentage point in independent mean TIR.

All 225 checked trajectories satisfied the specified safety limits, with no glucose below 70 mg/dL. Fresh meal seeds and a different final integrator can still produce different outcomes; these tests do not establish heldout safety or global optimality. This is a simulation benchmark formulation, not a clinical recommendation.
