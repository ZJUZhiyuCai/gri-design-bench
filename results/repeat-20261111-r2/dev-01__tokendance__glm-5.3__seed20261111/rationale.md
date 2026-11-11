# GRI static formulation design (dev-01)

## Goal
Maximize mean post-warmup TIR (70-180 mg/dL) on fresh meal scenarios for the
3 known patients, with hard safety: per-trajectory TBR70 <= 4%, TBR54 <= 1%,
and full-horizon minimum glucose >= 40 mg/dL (warmup day included in the
minimum-glucose check). Simulation benchmark only; not clinical advice.

## Formulation
Shared-cohort responsive basal rate:
rate(t) = theta_a * TDI * (relative_leak + Hill(Gf; ec50, hill_n)),
where Gf is interstitial glucose filtered by a first-order filter (tau_min),
flux applied with midpoint sampling every 3 min, capped by a finite reservoir
of theta_L * TDI units. No per-patient coefficients, no controller logic, no
external boluses.

## Search
`search.py` (reproducible, fixed RNG seed) runs a coarse randomized search in
log-space over (theta_a, relative_leak, ec50_mg_dl, hill_n, tau_min) with
theta_L sized to avoid reservoir depletion, screens every candidate on the
safety constraints across all training variants, refines locally, then
re-validates the finalist on extra fresh meal seeds (robustness margin for
the unseen evaluation seeds) and saves atomically.

## Results
(to be filled after search completes)

## Caveats
Zero rule makes safety dominate: candidates are only ranked on TIR after
passing the hard screen with margin, and finalists are checked on seeds not
used for selection.
