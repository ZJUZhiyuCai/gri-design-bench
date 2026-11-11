# GRI static formulation rationale (dev-05)

Cohort: adolescent#004 (TDI 35.25 U), adolescent#005 (34.00 U), adolescent#006 (49.58 U).
Three days, warmup 1440 min; TIR/TBR computed on post-warmup minutes only; minimum
glucose enforced over the full horizon.

Design choice: responsive (Hill-shaped glucose-dependent release) rather than constant.
A constant reservoir cannot reduce release when glucose falls, so it either over-delivers
(hypoglycemia, hard safety gate) or under-delivers (hyperglycemia, low TIR). The
responsive mode keeps a floor of `theta_a * relative_leak` U/min and adds a
glucose-dependent term that turns on as filtered interstitial glucose rises above EC50,
which matches the finite-reservoir constraint: insulin is spent when it is needed and
conserved when glucose is low.

Initial parameter reasoning:
- `theta_a` small: amplitude scales with native TDI, and adolescents are insulin
  sensitive; even 0.001 U/min per U of TDI is a large absolute basal for the largest
  patient.
- `relative_leak` at its lower bound (1.5) minimizes the unavoidable floor and gives the
  Hill term the widest useful dynamic range.
- `ec50_mg_dl` near the lower half of the target band so the response begins before
  hyperglycemia develops.
- `hill_n` moderate for a smooth, non-chattering transition.
- `tau_min` a few minutes to filter postprandial spikes without delaying the response.
- `theta_L` large enough that the reservoir does not empty before day 3.

This checkpoint is a starting point; the accompanying search.py refines it by grid /
local scan over the training seed and the two challenge variants, keeping the hard safety
gates (TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40 mg/dL) as feasibility constraints and
selecting the feasible candidate with the highest mean TIR.
