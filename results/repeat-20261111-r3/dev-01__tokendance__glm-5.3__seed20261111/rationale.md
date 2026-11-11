# GRI static formulation design — rationale (dev-01)

**Goal.** Maximize mean post-warmup TIR (70–180 mg/dL) on fresh meal seeds for the known
3-patient cohort, subject to TBR70 ≤ 4 %, TBR54 ≤ 1 % and min glucose ≥ 40 mg/dL
(full horizon incl. day 1).

**Formulation.** Responsive open-loop rate with shared coefficients:
rate = θa·TDI·(relative_leak + Hill(filtered interstitial glucose)) U/min, with
first-order filtering (tau) and finite reservoir θL·TDI.
Initial checkpoint: moderate amplitude with a basal leak that covers fasting
needs; Hill term supplies post-meal increments. Search then refines θa, EC50,
n, tau, leak and θL via time-budgeted coordinate descent on the fast RK4
evaluator with hard-safety penalties.
