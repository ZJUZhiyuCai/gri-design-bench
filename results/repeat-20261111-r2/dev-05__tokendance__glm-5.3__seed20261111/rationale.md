# GRI dev-05 formulation rationale (initial checkpoint)

Cohort: adolescent#004/#005/#006, shared responsive shape. Levers: basal floor
(relative_leak x theta_a x TDI) plus a Hill feedback on low-pass filtered
interstitial glucose (EC50, hill_n, tau). Reservoir load set high enough that the
cap never binds. Search: penalised random/LHS search on the training seed with
safety margins (TBR70, TBR54, min glucose), then multi-seed validation.
This checkpoint holds the working example; final parameters follow the search.
