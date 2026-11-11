# GRI formulation rationale — dev-04

## Submitted formulation

The design is a **responsive**, cohort-shared formulation with
`theta_a=0.0009`, `relative_leak=0.5124966150526034`, `ec50_mg_dl=260`,
`hill_n=3`, `tau_min=2`, and `theta_L=1.25`. For each patient, the simulator
therefore computes amplitude as `0.0009 × native TDI` and the finite reservoir
as `1.25 × native TDI`. There are no patient-specific fitted coefficients,
boluses, external insulin, or online controller additions.

The minimum permitted relative leak reduces non-glucose-responsive exposure,
while the maximum permitted load avoids premature reservoir depletion over
three days. A moderately steep Hill response and short glucose filter provide
additional release at elevated glucose without the severe late hypoglycemia
observed during screening with higher amplitudes and lower EC50 values.

## Search and selection

I used the public RK4 experiment for broad parameter screening, then refined
around the promising amplitude/EC50/Hill-exponent region. The scoring function
penalized TBR and low full-horizon glucose before rewarding TIR. Selection did
not rely on the training seed alone: the five leading refinement candidates
were evaluated on three disjoint meal seeds (`8111004`, `9111004`, `10111004`)
and all three variants, giving 27 additional trajectories per candidate.
Among candidates with zero observed TBR, training-style feasibility, and a
validation minimum of at least 70 mg/dL, I selected the highest fresh-scenario
mean TIR. `search.py` reproduces this final refinement and selection and uses
atomic design checkpoints.

## Observed checks

For the selected design:

* **Native dopri5 training check (9 trajectories):** mean TIR **28.3218%**,
  maximum trajectory TBR70 **0%**, maximum trajectory TBR54 **0%**, and
  full-horizon minimum glucose **78.3604 mg/dL**.
* **Fresh-seed RK4 validation (27 trajectories):** mean TIR **27.6080%**,
  maximum trajectory TBR70 **0%**, maximum trajectory TBR54 **0%**, and
  full-horizon minimum glucose **76.5768 mg/dL**.

The native check closely matched the fast-integrator training result
(28.3218% TIR and 78.3603 mg/dL minimum), supporting numerical consistency.
These results motivated a substantial margin above the 40 mg/dL hard floor and
zero observed TBR, rather than pushing amplitude to the training safety edge.
They do not guarantee performance on unseen meal seeds; final outcomes remain
subject to independent native simulation.

This is solely a simulation-benchmark formulation, not a clinical treatment
recommendation.
