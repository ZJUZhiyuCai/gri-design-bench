# GRI static formulation design (dev-06) — draft rationale

Simulation benchmark only; not a clinical recommendation.

Goal: maximize mean post-warmup TIR in [70,180] mg/dL on unseen meal seeds,
subject to per-trajectory TBR70 <= 4%, TBR54 <= 1%, and full-horizon
minimum plasma glucose >= 40 mg/dL (day 1 counts for the minimum).

Approach: a single shared responsive law
rate = theta_a * TDI * (relative_leak + Hill(G_filtered)),
Hill = 1/(1+exp(n*(log(EC50)-log(G_filtered)))), first-order filter tau,
midpoint flux every 3 min, finite reservoir theta_L * TDI.

Initial operating point: a basal-like floor (relative_leak) sized near the
children's basal requirement, EC50 near the mid-100s mg/dL so the Hill term
switches on around the postprandial range and off below ~100, moderate
sharpness (hill_n) and a short-but-not-instant filter (tau_min) to blunt
noise-driven over-delivery. theta_L caps total 3-day delivery to limit
stacking and hypoglycemia risk.

Search: reproducible seeded coordinate/pattern search over the bounded
parameters using the public cached Experiment (3 patients x 3 training
variants), prioritizing feasibility margins (TBR70, TBR54, min glucose)
before mean TIR.
