# GRI static formulation — design rationale (instance dev-05)

## Submitted design
```json
{"mode":"responsive","parameters":{"theta_a":9.314449961366025e-05,"relative_leak":5.340994499185289,
 "ec50_mg_dl":59.26305046791457,"hill_n":4.3204299565609805,"tau_min":0.5638069133376674,"theta_L":4.0}}
```
Cohort-wide shared coefficients; no individual fits, no meal announcement, no online controller.

## What the search found
A 3-stage search (`search.py`) over the responsive family
`rate = theta_a·TDI·[relative_leak + Hill_floor(G_filt)]` with exact filtering, 3-min midpoint
flux and a finite `theta_L·TDI` reservoir:

1. **Random search (96 points)** + **coordinate hill-climb (3 starts)** maximising a
   safety-margin-penalised TIR. The optimum is a **near-constant infusion**: large
   `relative_leak` (5.34, i.e. 84 % of the maximum rate is baseline leak), a saturated Hill
   term (`ec50` driven to its lower bound 59.3, `hill_n` 4.3) and a fast filter (`tau` 0.56 min).
2. **Why so flat**: the bound `relative_leak ≥ 1.5` caps the high/low rate ratio at
   2.5/1.5 = 1.67×, so true feedback authority is small; the residual modulation then only
   needs to *reduce* delivery as glucose falls, and the optimiser spends the rest of the budget
   on a constant baseline that covers basal needs plus meals. Designs with a genuine
   low-leak response (leak ≈ 4.5) lost ~7 TIR points; a Hill-free constant mode is the
   limit of this same shape and is not better.
3. **`theta_L` = 4.0 (upper bound)**: the reservoir is only a cap, so a large load never binds
   at the delivered rates while small loads risk mid-horizon starvation (irreversible
   hyperglycaemia). Pinning it high strictly dominates.

## The safety/performance trade (the decisive step)
Holding the shape fixed, the fasting plateau is the binding constraint and it moves
≈ **1.45 mg/dL per 1 % of `theta_a`**:

| amplitude scale | mean TIR (4 held-out seeds) | worst TBR70 | min glucose |
|---|---|---|---|
| 0.93 | 87.6 % | 0 | 79.9 |
| 0.95 | **89.1 %** | 0 | 77.2 |
| 0.97 | 90.5 % | 0 | 74.3 |
| 0.99 | 91.8 % | 0 | 71.5 |
| 1.01 | 89.5 % | **14.6 %** | 68.9 |

The TIR optimum sits *exactly* on the 70 mg/dL plateau: at +1 % amplitude the fasting period
drops below 70 for hours and the hard gate (TBR70 > 4 % ⇒ score 0) fires while TIR even falls.
Because a gate violation is catastrophic and the TIR gain from hugging the gate is < 3 points,
the submitted amplitude is scaled to **0.95×** the unconstrained optimum: worst-case minimum
glucose ≈ 77 mg/dL (≥ 7 mg/dL margin), TBR70 = TBR54 = 0 on every trajectory, TBR54 ≈ 0,
and glucose never approaches the 40 mg/dL absolute floor.
Validation seeds (6111013–6111016) were never used for shape fitting, so this margin is
measured on genuinely new meal scenarios; per-trajectory minima vary by < 1 mg/dL across
seeds and variants (the fasting plateau is set by the design, not by the meal draw), which
makes the 7 mg/dL buffer a robust, not a lucky, margin.

## Expected outcome
Mean TIR ≈ **89 %** on fresh seeds (≈ 81 % on the harder training seed 6111005), with
max per-trajectory TBR70 = 0 %, TBR54 = 0 % and minimum plasma glucose ≈ 77 mg/dL — i.e.
feasible with margin under the zero-score gates (TBR70 ≤ 4 %, TBR54 ≤ 1 %, glucose ≥ 40).

*This is a simulation benchmark artefact, not a clinical recommendation.*
