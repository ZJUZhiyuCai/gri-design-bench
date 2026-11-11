# GRI static formulation design (dev-02, adolescent#001-003)

## Formulation
Open-loop-per-patient responsive microbolus pump: rate U/min = theta_a*TDI*(relative_leak + hill(filtered interstitial glucose)),
first-order filter (tau), 3-min control interval, finite reservoir theta_L*TDI for the 3-day run.
Safety-first: hyperglycemia-driven delivery with strong sigmoid shutoff below ec50 keeps time-below-range near zero.

## Search
Multi-seed safe-TIR maximization with the public fast RK4 trainer, verified against per-trajectory TBR70/TBR54/min constraints
on ordinary/missed_lunch/large_dinner variants plus extra random meal seeds for robustness (final eval uses fresh seeds).
Details in search.py.
