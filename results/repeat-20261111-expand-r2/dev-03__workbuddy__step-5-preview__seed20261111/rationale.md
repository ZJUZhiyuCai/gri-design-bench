# Design rationale (initial checkpoint)

Static responsive formulation shared by the whole cohort (dev-03: child#001-003).

- Objective: maximize mean TIR in [70,180] mg/dL over post-warmup minutes on NEW meal seeds,
  subject to hard safety gates (TBR70<=4%, TBR54<=1%, min glucose>=40 mg/dL).
- Structure: rate = theta_a*TDI*(relative_leak + Hill(filtered IG)), exact first-order
  filtering (tau_min), 3-minute midpoint flux, finite reservoir = theta_L*TDI.
- Strategy: (1) establish a safe basal-only operating point (theta_a->0, small theta_L),
  (2) add just enough glucose-responsive gain to lift TIR while keeping the leak term
  bounded so the controller cannot drive hypoglycemia, (3) verify on custom fresh seeds
  and the day-2 missed-lunch / large-dinner challenges, (4) prefer designs with margin
  on the safety gates since evaluation uses unseen meal seeds.
- The 3-day first day is warmup (excluded from TIR/TBR) but included in the minimum
  glucose gate, so the reservoir must also be safe on day 1.
