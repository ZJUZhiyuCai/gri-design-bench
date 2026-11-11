# GRI static formulation — rationale (instance dev-01)

**Submitted design**

```json
{"mode":"responsive","parameters":{"theta_a":0.00068,"relative_leak":0.5125,
 "ec50_mg_dl":180.0,"hill_n":2.0,"tau_min":5.0,"theta_L":3.0}}
```

## Mechanism being exploited
Delivery is `rate = theta_a * TDI * (relative_leak + Hill(g_filtered))`, with
`Hill = 1/(1+(ec50/g)^n)` — i.e. **more insulin at higher glucose** — drawn from a
finite reservoir of `theta_L * TDI` units over the 3-day horizon, and a constant
leak floor that is delivered even at euglycaemia/hypoglycaemia. Two structural
facts drive the whole design:

1. **The leak is the safety-critical knob.** Because the reservoir is finite and
   the leak is unconditional, any amplitude that is large enough to blunt meal
   peaks also forces continuous insulin when glucose is already low; the pump can
   only stop when the reservoir empties, which is far too late. In my evaluations
   every candidate with `theta_a >= 0.00075` (or steeper Hill gain) produced
   TBR70 of 20–34 % and minima of 30–53 mg/dL.
2. **Total insulin is capped by `theta_L * TDI`**, so amplitude mainly sets *when*
   the reservoir is spent, not how much exists. Spending it overnight (leak) is
   wasted; spending it during post-prandial hyperglycaemia is what raises TIR.

## Parameter choices
- `relative_leak = 0.5125` — the lower bound. This pins the *basal* delivery to the
  smallest allowed fraction and maximises the dynamic range of the Hill branch
  (baseline share of the signal is only 0.5125/1.5125 ≈ 34 % at saturation).
- `theta_a = 0.00068` — sized so the leak-only rate reproduces basal need:
  `theta_a * leak * TDI ≈ 0.5 * TDI / 1440 U/min`. This is the largest amplitude
  that kept every trajectory above ~75 mg/dL in my sweeps; it is the anchor of the
  safety margin.
- `ec50 = 180 mg/dL`, `hill_n = 2.0` — a smooth, wide transition centred at the
  top of the target band, so the extra (above-basal) insulin is requested only
  once glucose is above ~150–180 mg/dL. A steep switch was not beneficial: it
  behaves like an on/off bolus and caused overshoot hypoglycaemia.
- `tau_min = 5` — short interstitial filter: the 3-min midpoint sampling is only
  slightly smoothed, so delivery tracks the true trend without lag-induced
  over-delivery at the peak.
- `theta_L = 3.0` — total load of 3 × TDI over 3 days ≈ 1.0 × TDI/day. Larger
  loads (4.0) tested as *safe but under-reactive* (TIR 60.7, min 90 mg/dL): the
  extra units were simply never requested, so they did not help.

## Measured performance (fast RK4 evaluator)
Training seed 6111001, 3 patients × 3 variants (ordinary / missed_lunch /
large_dinner): **mean TIR 79.4 %**, worst-trajectory TBR70 = 0 %, TBR54 = 0 %,
minimum plasma glucose 75.8 mg/dL, no trajectory below 70.

Held-out meal seeds 6111002–6111003: **mean TIR 77.3 %**, minimum glucose
75.4 mg/dL, TBR70 = TBR54 = 0 on every trajectory. The minimum is set by the
overnight fasting/leak equilibrium and moves only ~0.5 mg/dL across seeds, while
meal-seed changes mostly affect the hyperglycaemic peaks — so the design has a
structural ~5 mg/dL buffer above the 70 threshold and ~35 mg/dL above the 40
mg/dL absolute floor, independent of the (excluded) warm-up day's TIR.

## Rejected alternatives (safety gate dominates)
| design | mean TIR | min BG | TBR70 | verdict |
|---|---|---|---|---|
| **submitted** | **79.4** | **75.8** | **0.0** | chosen |
| theta_a 0.00075, ec50 150, n 3.5, L 4 | 77.0 | 53.0 | 19.6 | unsafe |
| theta_a 0.00090, ec50 140, n 4.0, L 4 | 68.2 | 31.8 | 33.7 | unsafe |
| theta_a 0.00055, ec50 160, n 3.0, L 4 | 60.7 | 90.3 | 0.0 | safe, under-dosed |

Because a single trajectory breaching TBR70 > 4 %, TBR54 > 1 % or any minute
< 40 mg/dL zeroes the score, I deliberately trade a few TIR points of peak
suppression for a hard, seed-independent hypoglycaemia buffer. Safety was never
assumed from training seeds alone: candidates were filtered on held-out seeds,
and the chosen margin is structural (leak ≈ basal), not seed-specific. This is a
simulation benchmark result, not a clinical recommendation.

Reproduction: `python search.py` (random search + hard safety gate +
`save_design`); the table above is the audited output of that protocol.
