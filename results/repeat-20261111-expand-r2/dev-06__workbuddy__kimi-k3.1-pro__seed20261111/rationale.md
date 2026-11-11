# GRI formulation rationale

A responsive Hill formulation was selected. Its glucose-dependent component
increases delivery around meals, while the sub-unity leak and finite reservoir
limit prolonged basal exposure. All six coefficients are shared; native TDI
only sets the cohort-patient amplitude and reservoir scaling as required.

The search used the public fast RK4 model, bounded global exploration followed
by local perturbations, and selection on the **mean** of three independent meal
seeds rather than training-seed performance alone. Candidates were checkpointed
only if all 27 patient/variant trajectories met every hard constraint. The
selected point had mean TIR 45.05% across those seeds (45.95%, 43.68%, 45.51%
by seed), with zero maximum TBR70/TBR54 on each seed. This multi-seed selection
was chosen to avoid relying on any presumed held-out safety guarantee.

The relatively high EC50 and moderate Hill exponent make delivery increase
mainly during hyperglycemia; the 6.56-minute filter reduces meal-spike latency,
and the approximately 2.10 TDI reservoir prevents unlimited multi-day release.
This is solely a simulation-benchmark design, not a clinical recommendation.
