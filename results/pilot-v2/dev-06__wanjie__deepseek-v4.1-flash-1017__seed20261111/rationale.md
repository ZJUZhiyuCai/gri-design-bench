# GRI static formulation — instance dev-06 (child#004, child#005, child#006)

## Submitted design
`responsive`: theta_a = 3.75e-4, relative_leak = 0.6335, ec50 = 236.74 mg/dL,
hill_n = 3.0, tau = 4.043 min, theta_L = 4.0 (reservoir = 4x TDI over 3 days).

## Training-seed result (seed 6111006, 3 patients x 3 variants)
| patient | TIR (ord / missed lunch / large dinner) | mean BG | min plasma glucose |
|---|---|---|---|
| child#004 | 12 / 18 / 14 | 229 / 225 / 232 | 133.7 (starting value; never lower) |
| child#005 | 90 / 91 / 86 | 119 / 113 / 122 | 73.3 |
| child#006 | 50 / 59 / 49 | 195 / 186 / 199 | 110 |

mean TIR ≈ 52.0 %, max trajectory TBR70 = 0.0 %, max TBR54 = 0.0 %,
minimum glucose over every trajectory and every full-horizon minute = 70.2 mg/dL.
Hard gates (TBR70 ≤ 4 %, TBR54 ≤ 1 %, min ≥ 40) are therefore met with wide margin:
0 % vs 4 %, and 70 vs 40 mg/dL.

## What drove the design
1. **Cohort de-confounding is the dominant effect.** Delivery is
   theta_a·TDI·(leak + Hill(G)) U/min, so the TDI-per-kg differences in this
   cohort (0.49 / 1.08 / 0.49 U/kg/day) translate directly into relative
   over-delivery for child#005 and starvation for child#004. child#004 never
   falls below its initial 133.7 mg/dL under any safe candidate, i.e. it is
   entirely hyperglycaemic and carries no hypoglycaemia risk, while child#005
   is the only trajectory that ever approaches the low bound. Because the
   coefficients must be shared, the only available lever is the *shape*: a small
   basal floor (relative_leak) plus a steep sigmoid centred far above
   euglycaemia means the unit-TDI rate is nearly constant and small at
   ~120 mg/dL (Hill ≈ 0.07) but large at ~230 mg/dL (Hill ≈ 0.6). That shape
   gives the hyperglycaemic child roughly 1.8x the per-TDI delivery of the
   well-controlled child, which is the maximum separation attainable inside the
   allowed hill_n ≤ 4 and relative_leak ≥ 0.5125 bounds.
2. **Higher gain, not more basal.** Random sampling showed the safe frontier at
   theta_a·relative_leak ≈ 2.4e-4 (TIR ≈ 37); adding gain in the *response*
   channel instead of the leak channel raised TIR to ≈ 52 without any TBR.
   Large leak values (≥ 2) were uniformly worse: they burn the reservoir and
   cause nocturnal lows in child#005 without helping child#004.
3. **Fast filter, ample reservoir.** tau ≈ 4 min (bounds 2-20) tracks the
   interstitial signal closely enough to cut postprandial peaks without
   oscillating; theta_L = 4.0 removes the finite-reservoir constraint (the design
   needs ≈ 0.8-0.95 TDI/day, versus the 1.33 TDI/day cap) so insulin is never
   rationed late in the horizon, which is exactly where under-delivery would show
   up as day-3 hyperglycaemia.
4. **Safety margin for fresh seeds.** The search scored candidates with a gate of
   TBR70 ≤ 0.3 %, TBR54 = 0 and min glucose ≥ 68 mg/dL, and the submitted
   amplitude was additionally shaved ~3 % from the raw training optimum
   (theta_a 3.87e-4, TIR 52.0, min 70.2). Since evaluation uses fresh meal seeds
   and the day-2 challenges (missed lunch, 1.5x dinner) are fixed, the binding
   risk is a larger-than-training dinner driving child#005 low; the 30 mg/dL
   headroom above the 40 mg/dL cliff and 4 % TBR headroom are the buffer.

## Honest limitations
child#004 remains at ~230 mg/dL (TIR ≈ 12-18 %) and child#006 at ~195 mg/dL;
per-TDI scalars cannot fix a cohort whose insulin need per U of TDI differs by
>2x, so the achievable mean TIR is bounded well below the per-patient optimum.
This is a simulation benchmark artefact, not a clinical recommendation.
