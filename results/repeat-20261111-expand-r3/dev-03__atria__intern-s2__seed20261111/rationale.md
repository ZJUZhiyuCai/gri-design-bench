# Rationale — dev-03 (child#001/002/003)

## Design choice: responsive (feedback) mode
A constant-rate open-loop profile cannot react to the missed-lunch and 50%-larger-dinner
challenges: the same insulin is delivered regardless of glucose, so either the large dinner
drives postprandial hyperglycaemia or the missed lunch drives hypoglycaemia. The responsive
formulation modulates delivery with filtered interstitial glucose, so it naturally suppresses
delivery when glucose falls (protecting against the missed lunch) and increases it after the
large dinner.

## Parameter roles
- `theta_a` (amplitude, U/min per unit TDI): scales the whole delivery curve.
- `relative_leak`: glucose-independent floor; sets the effective basal-like rate.
- `ec50_mg_dl`, `hill_n`: position and steepness of the glucose-responsive sigmoid.
- `tau_min`: first-order lag on interstitial glucose; larger tau = smoother, less reactive.
- `theta_L`: reservoir size as a multiple of TDI; total deliverable insulin over 3 days.

## Safety-first reasoning
The hard gate is per-trajectory: TBR70 <= 4%, TBR54 <= 1%, and every full-horizon minute
>= 40 mg/dL. Hypoglycaemia is driven by (a) too much insulin during/after a meal that is
then missed, and (b) exhausting the reservoir too early so that no insulin is available
later. We therefore keep the leak floor modest, place the EC50 near the upper end of the
target band so the response is mild at euglycaemia and only rises on clear hyperglycaemia,
and use a moderate tau to avoid over-reacting to single excursions.

## Search procedure
A coarse grid over the six parameters was evaluated with the fast RK4 trainer
(`gri_bench.physiology.fast_trace`), then refined by local random perturbation around the
best feasible point. Candidates were ranked by mean post-warmup TIR with any safety
violation zeroed (matching the benchmark's `safe_tir`). The final point was re-checked
against all 3 patients x 3 training variants.

## Notes
All coefficients are shared across the cohort; no patient-specific fitting was used.
This is a simulation benchmark design, not a clinical recommendation.
