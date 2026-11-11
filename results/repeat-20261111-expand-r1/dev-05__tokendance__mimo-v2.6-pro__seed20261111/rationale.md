# GRI static formulation design (dev-05)

Goal: maximize mean post-warmup TIR in [70,180] mg/dL over fresh meal seeds,
with zero tolerance for TBR70 > 4%, TBR54 > 1%, or any minute below 40 mg/dL.

Approach: cohort-shared responsive basal, searched with seeded random search
plus coordinate refinement on the training scenarios. Initial placeholder
design; final parameters reported in design.json after search.
