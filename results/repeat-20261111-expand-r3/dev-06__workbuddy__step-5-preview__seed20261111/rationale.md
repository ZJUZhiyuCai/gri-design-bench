# GRI static formulation rationale (instance dev-06, 3 patients x 3 day-2 challenges)

## Objective and gates
Maximise the mean percentage of post-warmup plasma glucose in [70, 180] mg/dL on
new meal scenarios, subject to hard gates that zero the score if **any**
patient/scenario shows TBR70 > 4%, TBR54 > 1%, or any full-horizon minute below
40 mg/dL. Day 1 is excluded from TIR/TBR but included in the minimum-glucose
check, so the design must also be safe across the unseen warmup day.

## Design form
Responsive static formulation, shared by the whole cohort:

    rate(t) = theta_a * TDI * [ relative_leak + Hill(filtered interstitial G) ]
    Hill    = 1 / (1 + exp(hill_n * (ln EC50 - ln G_filtered)))
    load     = theta_L * TDI  (finite reservoir, mass-conserving 3-min flux)

The per-patient scaling by native TDI is the only personalisation allowed, and it
is a property of the formulation rather than a fitted individual coefficient.

## Search
`search.py` scores candidates on the cached training cohort (3 patients x 3
variants, seed 6111006) with the public fast RK4 harness and runs a multi-start
compass search with geometrically shrinking steps. The objective penalises the
safety gates *with margin* (targets TBR70 <= 3.0%, TBR54 <= 0.5%, min G >= 45
mg/dL) because verification uses fresh meal seeds; a design sitting exactly on a
gate would flip to zero on an unseen scenario.

## Selected parameters
| parameter | value | role |
|---|---|---|
| theta_a | 0.00019 | rate amplitude per unit TDI (U/min) |
| relative_leak | 1.13744 | glucose-independent basal fraction |
| ec50_mg_dl | 128.83 | half-maximal glucose of the Hill term |
| hill_n | 2.957 | steepness of the glucose responsiveness |
| tau_min | 8.246 | first-order filter time constant |
| theta_L | 4.0 | reservoir load = 4 x TDI (U) |

Training-cohort outcome: mean TIR 44.5%, worst TBR70 2.9%, worst TBR54 0.0%,
minimum glucose 69.2 mg/dL - feasible on all three gates.

## Reasoning behind the choices
* **Small theta_a (1.9e-4 U/min per U TDI).** A basal-like amplitude with a
  large glucose-dependent gain is what keeps postprandial peaks down without
  flooding the interstitium; amplitudes an order of magnitude larger drove every
  trajectory into severe hypoglycaemia in the initial random screen.
* **EC50 near 129 mg/dL with hill_n ~ 3.** The half-maximal point sits just below
  the top of the target band, so the controller is nearly saturated at 180 mg/dL
  and steeply reduces its gain below 70 mg/dL. That is exactly the asymmetry the
  TBR gates demand: strong suppression of hyperglycaemia, weak action in
  hypoglycaemia.
* **tau_min ~ 8.2 min.** Fast enough to track a 3-minute flux update without
  amplifying CGM/interstitial lag-induced oscillation; longer filters delayed
  the postprandial response and cost TIR.
* **relative_leak ~ 1.14.** Provides a non-trivial glucose-independent basal
  term. Pure-leak-free designs over-react to the Hill term; a large leak behaves
  like a constant basal and loses the day-2 challenge protection.
* **theta_L at the upper bound (4.0).** With theta_a * 4320 min ~ 0.82 x TDI the
  three-day reservoir can never be exhausted, so the cap is inactive and the
  maximum permitted load is the risk-free choice.

## Limitations
Only one training meal seed was visible, so the numbers above are diagnostic; the
final verifier uses native dopri5 on fresh seeds. The design keeps roughly
1.1 pp of headroom on the TBR70 gate and a large margin on TBR54 and the 40 mg/dL
floor. This is a simulation benchmark result, not a clinical recommendation.
