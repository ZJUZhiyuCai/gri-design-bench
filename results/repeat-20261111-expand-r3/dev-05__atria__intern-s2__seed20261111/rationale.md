# Rationale — dev-05 (adolescent#004, #005, #006)

## Design choice: responsive mode
A constant-rate reservoir cannot adapt to meals or to the large inter-patient
insulin-sensitivity spread in adolescents (TDI 34–50 U), so it either under-doses
(post-prandial excursions) or over-doses overnight (TBR violations). The
responsive shape adds a glucose-dependent term while keeping every coefficient
shared and the reservoir finite.

## Parameter roles
- `theta_a` scales the amplitude by native TDI (U/min), so the same shape
  auto-scales to each patient's insulin requirement.
- `relative_leak` sets the glucose-independent floor. It must be low enough that
  overnight fasting glucose in insulin-sensitive adolescents stays above 54 mg/dL,
  but non-zero so the reservoir is not exhausted only by meals.
- `ec50_mg_dl` / `hill_n` set the glucose threshold and sharpness of the
  additional release. The transition is placed near the upper half of the target
  range so that post-prandial glucose recruits extra insulin while fasting glucose
  sits below the threshold (minimal basal).
- `tau_min` filters interstitial glucose. A moderate tau damps CGM noise and
  prevents over-delivery on transient excursions; it also shapes the phase lag
  relative to the meal.
- `theta_L` sets the total reservoir (theta_L * TDI). It is sized to cover three
  days including the missed-lunch and 50%-larger-dinner challenges without
  running dry, while remaining inside the material bound.

## Safety-first search
Feasibility (TBR70 <= 4%, TBR54 <= 1%, every full-horizon minute >= 40 mg/dL) is
a hard gate: any infeasible candidate scores 0. The search therefore explores the
low-leak, moderate-amplitude region first, then refines by coordinate ascent.
The constant-mode baseline is evaluated for comparison.

## Known-cohort limitation
Only the three listed patients and the single training seed are used for
selection; final evaluation uses fresh meal seeds. The shared-coefficient,
TDI-scaled formulation is therefore the only generalisation mechanism — no
patient-specific fitted coefficients are used.
