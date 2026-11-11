# GRI dev-02 rationale (initial draft; will be updated)

Structure: responsive rate theta_a*TDI*(relative_leak + Hill(filtered interstitial glucose)).
- Leak term supplies basal insulin; Hill term adds postprandial correction above EC50.
- tau filters CGM-ish interstitial glucose; steep hill_n approximates threshold bolus.
- theta_L*TDI finite reservoir sized to cover 3 days of basal + meals with margin.
Objective: maximize mean TIR on fresh meal seeds subject to per-trajectory
TBR70<=4%, TBR54<=1%, full-horizon min glucose>=40 (use strict internal margins).
Search: coarse randomized sweep then pattern refinement on the training seed,
validated on extra fresh meal seeds (see search.py). No per-patient coefficients.
