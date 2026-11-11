# Rationale (initial)

Placeholder rationale. The formulation is a single glucose-responsive
long-acting insulin shared by the whole cohort, parameterised in units of
each patient's native total daily insulin (TDI):

* release-rate amplitude `theta_a * TDI` (U/min),
* shape `relative_leak + Hill(filtered interstitial glucose; ec50, hill_n)`,
* first-order filter `tau_min`,
* finite reservoir `theta_L * TDI` (U) shared over the 3-day horizon.

Because `relative_leak >= 1.5` and the Hill term is at most 1, the
glucose-responsive dynamic range is intrinsically modest; the dominant
levers are the average basal rate and the total load. The search maximises
post-warmup TIR subject to hard safety constraints (TBR70 <= 4%,
TBR54 <= 1%, minimum glucose >= 40 mg/dL).
