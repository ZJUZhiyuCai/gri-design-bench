# GRI static formulation design (dev-05)

Cohort: adolescent#004/005/006. Objective: mean TIR (plasma glucose in [70,180]
mg/dL over days 2-3, day 1 warmup excluded) on unseen meal scenarios, subject to
hard safety gates (TBR70<=4%, TBR54<=1%, no minute below 40 mg/dL anywhere).

Formulation: a single responsive "material" release law shared by the cohort.
Insulin delivery rate (U/min) = theta_a*TDI * (relative_leak + Hill(filtered
interstitial glucose)), where the filter is a first-order lag with time constant
tau_min on the CGM-visible compartment, flux is evaluated at the 3-minute
midpoint, and the total released load is theta_L*TDI U from a finite reservoir.

Search: coordinate/random search over the six shape parameters (and the
constant-rate alternative), scored on mean TIR with a penalty on safety-gate
violation, validated across multiple meal seeds to avoid overfitting the
training seed. See search.py for the reproducible procedure.
