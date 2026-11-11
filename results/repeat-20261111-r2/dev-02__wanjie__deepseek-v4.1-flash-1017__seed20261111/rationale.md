# GRI static formulation — instance dev-02 (adolescent#001–003)

## Submitted design
```json
{"mode":"responsive","parameters":{"theta_a":0.0002122,"relative_leak":1.7297525,
 "ec50_mg_dl":92.9023113,"hill_n":2.0071485,"tau_min":1.7025977,"theta_L":4.0}}
```
Training metrics (3 patients × 3 variants, seed 6111002, fast RK4):
mean TIR **81.26 %**, max trajectory TBR70 0.00 %, max TBR54 0.00 %, minimum glucose 70.1 mg/dL,
feasible = true. Per-trajectory TIR: #001 98.3/99.4/98.3, #002 73.7/85.6/69.9, #003 64.3/80.5/61.4.

## Mechanism / key structural findings
* Measured flux is `theta_a*TDI*[relative_leak + sigmoid(hill_n*(ln ec50 − ln G_filt))]`, i.e. the Hill
  term **rises as glucose falls** (inverse of a corrective controller). Any large Hill contribution
  therefore adds insulin precisely during a downward excursion — pure hypoglycaemia risk with no TIR
  benefit. The design consequently uses a low-ish EC50 (93 mg/dL, near the low bound region) and a
  moderate Hill gain so that `relative_leak` (1.73) dominates: flux ≈ 0.00037·TDI U/min with only a
  small, smooth glucose modulation.
* `theta_L` only enlarges the finite reservoir (total deliverable = theta_L·TDI). At the chosen flux the
  3-day consumption is ≈1.9·TDI, well under the cap, so depletion never occurs; `theta_L` is pinned at
  its upper bound (4.0) as a pure slack variable — it cannot improve control but can only prevent
  late-horizon starvation if the verifier's dopri5 trajectory draws more insulin.
* `tau_min` is kept short (1.7 min): the exact first-order filter mainly adds phase lag; short tau makes
  the midpoint flux behave like instantaneous glucose feedback, avoiding delayed over-delivery.
* Absolute amplitude scales with native TDI, which is the only permitted way to differentiate a small
  patient (#003, TDI 24.2 U) from a large one (#002, TDI 62.0 U); no per-patient coefficients used.

## Search procedure (see search.py)
Two-phase stochastic search over the six shared coefficients, all inside the instance bounds:
1. coarse random exploration parametrised by the *base flux* b = theta_a·relative_leak ∈ [1e-4, 4.5e-3]
   (log-uniform), with leak, EC50, n, tau sampled; theta_L fixed at its upper bound.
2. multiplicative coordinate refinement (log-normal perturbations, adaptive step 0.03–0.5) around the
   incumbent, accepting only strict improvements.
Objective: mean post-warmup TIR minus a heavy penalty that triggers on `max_tbr70 > 1 %`,
`max_tbr54 > 0.2 %` or `minimum_glucose < 60` (the official gate is looser), plus a graded margin term.
224 coarse+refine evaluations were consumed; a second pass re-weighted the margin term toward
`minimum_glucose ≥ 80`, which yields ~71 % TIR at nadir 82 — a deliberate, documented trade-off in
favour of the submitted point at 81.3 % TIR / nadir 70, since the hard gate is TBR70 ≤ 4 %,
TBR54 ≤ 1 % and glucose ≥ 40 (large headroom), while TIR is the objective.

## Safety reasoning and residual risk
The only binding trajectory is #002 (nadir 70.1 mg/dL, TBR70 0 despite the 70 mg/dL line being touched,
because the nadir occurs pre-dawn and the trajectory re-enters range quickly). Fresh meal seeds shift the
post-absorptive nadir by roughly ±10 mg/dL, so a plausible worst case is a few % TBR70 — still inside the
4 % allowance — and nowhere near the 40 mg/dL hard floor on any horizon minute. Hypoglycaemia protection
is intrinsically weak in this formulation class (inverse Hill action, no boluses, no IOB awareness), so
the near-constant flux that dominates here is the safest operating point per unit of TIR.

Caveats: this is a simulation benchmark result, not a clinical recommendation; the coefficients are a
synthetic subrange of a prior fitted shape envelope, not a measured material, and no safety claim
transfers outside simglucose 0.2.11 with native RandomScenario meals.
