# GRI static formulation design (instance dev-06)

Cohort: child#004 (TDI 19.82 U), child#005 (TDI 40.93 U), child#006 (TDI 20.22 U).
3-day scenarios (ordinary / day-2 missed lunch / day-2 50% larger dinner), day 1 is
warmup (excluded from TIR/TBR, included in the minute-level >=40 mg/dL gate).

## Chosen formulation
Responsive rate `rate = theta_a*TDI*(relative_leak + Hill(Gf))` with
`Hill = Gf^n/(EC50^n+Gf^n)`, `Gf` = first-order filtered interstitial glucose
(tau_min), finite reservoir `theta_L*TDI`. Coefficients are shared; TDI scaling
individualises amplitude/load.

- Baseline (Hill=0) delivery = theta_a*relative_leak*1440 ~ 0.5 TDI/day: classic
  ~50% basal fraction, keeps fasting glucose near target without boluses.
- Hill term adds up to theta_a*TDI U/min at high filtered glucose, giving
  meal-time up-titration and day-2 large-dinner coverage; it self-limits as
  glucose falls toward EC50, which protects the day-2 missed-lunch window.
- EC50/hill_n set the gain curve; tau smooths sensor noise; theta_L=3 keeps the
  3-day reservoir non-empty while still capping cumulative insulin.
Safety gates enforced in search: per-trajectory TBR70<=4% (i.e. <=3 of 96
post-warmup samples <70), TBR54<=1% (0 samples <54), minute-level min >=40
mg/dL on all days including day 1.
