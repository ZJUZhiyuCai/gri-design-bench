# Design rationale (dev-01)

**Chosen design (responsive mode):** theta_a = 3.5e-4 U/min per U/min TDI,
relative_leak = 1.5, EC50 = 200 mg/dL, Hill n = 2, tau = 10 min,
theta_L = 4.0 (load = 4 x TDI, i.e. the maximum allowed reservoir).

## Reasoning

1. **The controller is a proportional, glucose-responsive basal release.** The
   instantaneous rate is theta_a x TDI x (relative_leak + Hill(filtered CGM)),
   and the total releasable insulin is capped at theta_L x TDI. The reservoir
   cap is the binding constraint: with theta_L = 4 the drug is essentially
   never exhausted over 3 days, so theta_L is set to its upper bound to avoid
   late-horizon under-delivery.

2. **The objective is dominated by theta_a.** A coarse sweep showed the cohort
   TIR rises steeply and then collapses as theta_a grows: 0.0002 -> 24% TIR,
   0.0005 -> 61%, and >= 0.001 -> total failure (hypoglycaemia, TBR70 = 100%).
   The feasible window is narrow, between roughly 2.6e-4 and 3.7e-4.

3. **Shape parameters are secondary.** A moderate Hill (n = 2, EC50 = 200) with
   tau = 10 min of first-order filtering gives a smooth, delayed response that
   attenuates post-prandial spikes without overshooting into hypoglycaemia;
   tau = 10 min suppresses noise while still reacting within a meal window.
   relative_leak = 1.5 keeps a non-trivial basal floor so fasting/night glucose
   does not drift high, and the Hill term dominates at high glucose.

4. **Safety margin.** The TIR peak on the training variants is near
   theta_a = 3.6e-4 (TIR ~87%, min glucose ~72 mg/dL); at 3.8e-4 the
   constraint TBR70 <= 4% is already violated. Because the evaluation uses fresh
   meal seeds (and the native dopri5 integrator), the submission is backed off
   to theta_a = 3.5e-4, which keeps the training minimum glucose ~74-78 mg/dL
   with zero TBR70/TBR54 - a deliberate buffer against seed-to-seed and
   integrator-to-integrator variability.

## Training results (seed 6111001, 3 patients x 3 variants)

| theta_a | mean TIR | min glucose | feasible |
|---|---|---|---|
| 0.00030 | 64.1 | 91.7 | yes |
| 0.00034 | 81.2 | 78.4 | yes |
| 0.00036 | 86.6 | 71.8 | yes |
| 0.00038 | 82.1 | 65.8 | no (TBR70) |
| **0.00035** | **~83** | **~75** | **yes** |

All constraints (TBR70 <= 4%, TBR54 <= 1%, minimum glucose >= 40 mg/dL) are
satisfied with margin at the submitted design.
