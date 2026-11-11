# GRI static formulation, instance dev-04 (adult#004, #005, #006)

## Submitted design
`mode = responsive`, shared coefficients for the whole cohort:

| coefficient | value | bound |
|---|---|---|
| theta_a | 3.0306e-4 (U/min per U TDI) | [0, 0.007] |
| relative_leak | 1.6669 | [0.5125, 5.5189] |
| ec50_mg_dl | 395.22 | [59.26, 816.11] |
| hill_n | 2.4971 | [0.588, 24] |
| tau_min | 0.9438 | [0.05, 20] |
| theta_L | 1.2266 | [0.4, 1.25] |

Result on the cached training experiment (3 patients x 3 variants, seed 6111004):
mean TIR **29.95 %**, max trajectory TBR70 **0 %**, TBR54 **0 %**, minimum
full-horizon glucose **90.8 mg/dL** -> feasible with a wide safety margin.

## What the engineering analysis showed
1. **The finite load, not the rate bound, is the active constraint.** Total
   insulin is `theta_L * TDI <= 1.25 * TDI` for the whole 72 h, i.e. at most
   ~0.42 TDI/day, well under the ~1 TDI/day these patients actually need. With a
   constant rate at that limit (`search.py scan`) glucose drifts up out of range
   and TIR is only ~9 %. In this model excursions above ~600 mg/dL are
   practically unrecoverable (uptake saturates), so the same fixed load is worth
   far more when delivered *before/while* glucose is high than after.
2. **Hence a glucose-responsive shape with a strong load concentration.** The
   Hill term adds insulin only in the hyperglycaemic region (EC50 ~395 mg/dL,
   n ~2.5), while the leak term keeps a small floor so that the rate is still
   non-zero at euglycaemia; the filter tau ~0.94 min means the response tracks
   the (3-minute) glucose signal almost instantaneously. Percent-of-TDI scaling
   of the amplitude makes the same shape comparable across the three very
   different TDIs (33.8 / 68.3 / 61.4 U).
3. **The safety gate dominates the objective.** Any trajectory with TBR70 > 4 %,
   TBR54 > 1 % or any minute < 40 mg/dL zeroes the score, so the search ranked
   candidates with explicit margin penalties (minimum glucose >= 65 mg/dL,
   TBR70 <= 1 %) and reused the same threshold for stage selection. Pushing the
   low-glucose rate above ~1e-3 x TDI/min (`search.py extremes`) empties the
   reservoir within a day and crashes to 20-35 mg/dL with TBR54 up to 4.5 %;
   the submitted design sits comfortably below that cliff (lowest full-horizon
   glucose ~91 mg/dL, zero minutes below 70).
4. **Held-out robustness.** Because evaluation uses fresh RandomScenario meal
   seeds, the chosen point was re-scored on four unseen seeds (18 extra
   trajectories): mean TIR 26.0-29.9 %, TBR70 = 0 %, minimum glucose ~91 mg/dL in
   every case, and a further 14 seeded perturbations on a two-seed objective
   found no improvement, i.e. the design sits on a flat, safe plateau rather than
   a knife edge. The final design also avoids relying on anything scenario
   specific: the missed-lunch and large-dinner variants are handled by the same
   feedback shape (they simply see lower/higher glucose).

## Honest caveats
* TIR remains modest (~30 %) because the allowed insulin load is roughly 40 % of
  daily need; this is a property of the material/load constraints, not of the
  tuning.
* Safety margins were checked with the fast RK4 surrogate (the same code path as
  the graded verifier's fast API) and across several meal seeds; the native
  dopri5 verifier may shift trajectories slightly, so ~30 mg/dL of headroom above
  the 40 mg/dL hard floor and zero TBR is kept deliberately.
* This is a simulation benchmark artefact, not a clinical recommendation.
