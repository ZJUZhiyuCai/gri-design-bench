# Rationale (initial draft)

Static formulation with a responsive basal rate, shared coefficients across the cohort.

- Rate amplitude = theta_a * native TDI (U/min).
- Load = theta_L * TDI (U) in a finite reservoir, consumed only by the delivered rate.
- Rate = amplitude * (relative_leak + Hill(filtered interstitial glucose)).
- Filtering is exact first-order on the interstitial glucose with time constant tau_min;
  midpoint flux is evaluated every 3 minutes.
- Objective: maximize mean TIR over days 2-3 (warmup day 1 excluded), subject to
  per-trajectory TBR70 <= 4%, TBR54 <= 1%, and minimum plasma glucose >= 40 mg/dL.
- Challenges: missed day-2 lunch and 50% larger day-2 dinner, so the design must
  tolerate both under- and over-delivery of carbohydrate.
- Constant mode (theta_c * TDI) is a fallback if the responsive rate cannot be made safe.
