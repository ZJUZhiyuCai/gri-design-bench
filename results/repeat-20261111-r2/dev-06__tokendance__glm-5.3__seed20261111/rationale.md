# GRI static formulation rationale (dev-06: child#004, #005, #006)

Shared responsive-rate design: rate = theta_a*TDI*(relative_leak + Hill(EC50,n) of
first-order-filtered interstitial glucose), finite reservoir theta_L*TDI, 3-min midpoint flux.

- The Hill sigmoid makes delivery rise with glucose (meal response) and fall toward the
  `relative_leak` floor when glucose drops below EC50, protecting against hypoglycemia.
- theta_L >= ~2.5 keeps the reservoir from capping basal-equivalent delivery over 3 days.
- Search maximizes mean TIR on the cached training scenarios (3 patients x ordinary /
  missed_lunch / large_dinner) with a soft penalty on TBR70/TBR54 and on minimum glucose,
  then validates on fresh meal seeds for robustness to unseen evaluation scenarios.
- Search code: /work/output/search.py (deterministic grid + coordinate refinement).
This is a simulation benchmark result, not a clinical recommendation.
