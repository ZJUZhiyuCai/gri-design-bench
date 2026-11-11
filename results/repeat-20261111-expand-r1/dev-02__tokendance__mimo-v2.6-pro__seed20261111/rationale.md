# GRI static formulation design (dev-02)

Simulation benchmark only; not a clinical recommendation.

Mode: responsive. Insulin rate = theta_a*TDI * (relative_leak + Hill(g_filtered)),
Hill = g^n/(g^n+ec50^n) with first-order filtered interstitial glucose (tau_min),
evaluated at 3-min midpoints, delivered from a finite reservoir of theta_L*TDI (U).

Initial candidate: a modest amplitude with leak ~1.2 keeps a basal-like floor while
the Hill term adds meal coverage; ec50 ~160 mg/dL and n ~4 concentrate the response
on hyperglycemia; tau ~6 min smooths CGM noise; theta_L=3.0 gives reservoir headroom
for 3 days so day-3 delivery is not truncated.

Search: seeded random search + local refinement over the shared cohort parameters,
maximizing mean TIR subject to hard safety (TBR70<=4%, TBR54<=1%, min>=40 mg/dL).
See search.py. This file is updated after search completes.
