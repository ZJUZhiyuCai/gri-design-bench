# GRI formulation rationale

## Selected formulation

A shared **responsive** formulation was selected. Its finite reservoir is
`theta_L * TDI`; release is `theta_a * TDI * (relative_leak + Hill(filtered
interstitial glucose))`. The Hill midpoint is near 102 mg/dL with moderate
cooperativity, so release falls strongly as glucose approaches the lower part
of the target range. The sub-minute glucose-filter time constant avoids adding
a material delay. No meals, boluses, patient-specific coefficients, or online
control rules are used.

## Search and safety criterion

The reproducible search in `search.py` uses log coordinates for positive scale
parameters and bounded differential evolution. Stage 1 searches all nine
training patient/challenge trajectories. Stage 2 averages performance over the
training seed and a fresh meal seed. Selection uses three further fresh seeds.
The objective penalizes TBR70 above 0.5%, TBR54 above 0.1%, and full-horizon
minima below 60 mg/dL, deliberately leaving margin to the actual limits of 4%,
1%, and 40 mg/dL. A small amplitude-sensitivity comparison is included because
increasing release eventually creates a sharp hypoglycemia boundary.

## Observed checks

For the final parameters, the fast simulator gave 78.43% mean TIR on 27
fresh-validation trajectories (seeds 8111002--8111004), with maximum TBR70 and
TBR54 both zero and minimum glucose 71.51 mg/dL. On the nine training
trajectories, the trusted native dopri5 path gave **86.89% mean TIR**, zero
TBR70/TBR54, and minimum glucose **71.98 mg/dL**. Every training trajectory
was feasible. These are simulation results for this benchmark, not a clinical
recommendation; fresh-seed performance remains stochastic, so conservative
safety margins were preferred over the slightly higher-TIR/high-amplitude
candidate.
