# Rationale (initial placeholder)

Responsive mode with shared coefficients across the cohort. Rate = theta_a * TDI * (relative_leak + Hill(filtered interstitial glucose)),
computed every 3 minutes with exact first-order filtering (tau_min), midpoint flux, and a finite insulin reservoir of theta_L * TDI units.
Initial guess: theta_a=0.002, relative_leak=1.0, ec50=150 mg/dL, hill_n=2, tau_min=10 min, theta_L=2.5.
To be refined by search (see search.py).
