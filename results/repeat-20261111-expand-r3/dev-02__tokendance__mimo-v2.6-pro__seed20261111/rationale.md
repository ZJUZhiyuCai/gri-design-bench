# GRI static formulation design (dev-02)

Goal: maximize mean TIR70-180 on unseen meal scenarios, hard-zeroed if any
patient/scenario has TBR70 > 4%, TBR54 > 1%, or any full-horizon glucose < 40.

Approach: shared responsive formulation
rate = theta_a * TDI * [relative_leak + Hill(tau-filtered interstitial glucose)],
Hill(g) = g^n / (g^n + ec50^n), midpoint flux every 3 min, finite reservoir
theta_L * TDI. Safety-first coordinate search over the instance bounds using the
training seed/variants, keeping wide margins below TBR limits because the
verifier uses fresh meal seeds and native dopri5 integration.

Initial candidate is a conservative mid-range point; refined by search.py.
