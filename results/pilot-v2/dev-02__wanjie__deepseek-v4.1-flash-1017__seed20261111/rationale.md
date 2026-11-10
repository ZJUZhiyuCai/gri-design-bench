# GRI static formulation for dev-02 (adolescent#001/#002/#003)

## Selected design
```json
{"mode":"responsive","parameters":{"theta_a":0.0004,"relative_leak":0.9,
 "ec50_mg_dl":200.0,"hill_n":2.0,"tau_min":10.0,"theta_L":4.0}}
```
Rate = 0.0004 x TDI x (0.9 + Hill(IG; EC50 = 200 mg/dL, n = 2)) U/min,
i.e. a fasting floor of ~0.36 x TDI/1000 U/min rising to ~1.9x that when
interstitial glucose is well above 200 mg/dL. Reservoir load = 4 x TDI
(full allowed cap) so the 3-day finite supply never binds.

Training-cohort result (3 patients x 3 variants, seed 6111002):
mean TIR **78.4 %**, max trajectory TBR70 **0 %**, TBR54 **0 %**,
minimum plasma glucose **72.3 mg/dL** -> feasible with margin
(per-trajectory TIR: #001 94/96/94, #002 72/79/67, #003 65/75/62).

## How it was reached
Sweep of theta_a x relative_leak x EC50 x hill_n (tau 10, theta_L 4) on the known cohort:

| theta_a | leak | EC50 | n | mean TIR | max TBR70 | min glc |
|---|---|---|---|---|---|---|
| 2e-4 | 1.5 | 200 | 2 | 39.7 | 0 | 105.8 |
| 3e-4 | 0.55 | 130 | 6 | 44.7 | 0 | 103.2 |
| 3e-4 | 0.9 | 130 | 6 | 72.8 | 0 | 81.4 |
| 4e-4 | 0.55 | 130 | 6 | 75.1 | 0 | 78.3 |
| 4e-4 | 0.9 | 130 | 2 | 84.7 | **16.8** | 57.7 |
| 4e-4 | 0.9 | 200 | 2 | **78.4** | **0** | 72.3 |
| 5e-4 | 1.5 | 120 | 2 | (infeasible, glucose crashed) | ~15 | <60 |

Key lessons:
1. **Leak sets the basal floor.** With relative_leak at/near its lower bound
   (0.51-0.55) the cohort is under-insulinised in the fasting state: adolescent#003
   stays > 200 mg/dL for all post-warmup days and mean TIR collapses to ~30-45 %.
   A leak of 0.9-1.5 x theta_a x TDI restores basal coverage.
2. **EC50, not the Hill exponent, controls hypo risk.** At EC50 = 130 the same
   amplitude delivered so much insulin on the falling limb of meals that
   trajectories sat below 70 mg/dL for 17-19 % of post-warmup time. Raising
   EC50 to 200 mg/dL (high-n Hill variants behave similarly, and are more
   brittle) removed all hypoglycaemia while keeping post-prandial control.
3. **Deliberate safety margin.** The selected point is one grid step away from an
   infeasible region (TBR70 ~17 %), and a fresh-seed evaluation can shift meal
   size/timing, so a design with zero TBR and a 72 mg/dL nadir on the training
   cohort is preferred over the nominally higher-TIR but violating neighbours
   (84.7 % TIR with 16.8 % TBR scores zero).
4. **theta_L at its upper bound (4.0).** The finite reservoir is a hard total
   dose budget: adolescent#003 (TDI 24.2 U) consumed ~2.5-3 x TDI over three
   days at these rates, so smaller loads would deplete and cause late
   hyperglycaemia (a reservoir-starved design at theta_L = 1 showed 0 % TIR on
   the last days).
5. tau = 10 min smooths the interstitial estimate, avoiding 3-minute
   bang-bang oscillations in the delivery rate without adding meal-peak lag.
   A sharper (>6 min equivalent delay) filter was not beneficial, and short
   taus reproduced the oscillatory over-delivery seen at EC50 = 130.

## Caveats
This is a simulation benchmark artefact, not a clinical recommendation. The
coefficients are shared across all three patients by rule; only the TDI scaling
is individual. Validation here used the single training meal seed plus the
three scenarios (ordinary, missed lunch, 1.5x dinner); fresh evaluation seeds
are expected to shift TIR somewhat, which is why the design is kept strictly on
the insulin-conservative side of the feasible ridge.
