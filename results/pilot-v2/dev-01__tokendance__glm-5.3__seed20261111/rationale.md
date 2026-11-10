# GRI static formulation design (dev-01)

Shared responsive-mode open-loop policy: insulin rate = theta_a * native TDI *
(relative_leak + Hill(filtered interstitial glucose)), finite reservoir
theta_L * TDI. Chosen by grid search on the 3x3 training trajectories with
hard-safety penalties. See search.py.
