# GRI static design — instance dev-05 (adolescents #004/#005/#006)

## Submitted design
```json
{"mode":"responsive","parameters":{"theta_a":0.00023,"relative_leak":2.15244,
 "ec50_mg_dl":144.300591,"hill_n":0.58804,"tau_min":0.835856,"theta_L":3.22858}}
```

## Mechanism / what each coefficient does here
Rate = theta_a*TDI * [relative_leak + Hill(G_filt)], capped by the finite
reservoir theta_L*TDI at every 3-minute update. Because the delivered load is
finite and much smaller than what the rate cap could push, the reservoir — not
the rate ceiling — is the binding resource over 72 h: theta_L fixes the total
insulin budget (3.23 x TDI over 3 days ~ 1.08 x TDI/day), and the shape terms
only decide *when* that budget is spent.
* `theta_L = 3.23` (near the upper bound 4.0): more total insulin budget directly
  lowers mean glucose for the hyperglycaemia-prone adolescents; values near 4
  bought little extra TIR once the budget stopped being rate-limited.
* `theta_a = 2.3e-4` with the baseline `relative_leak = 2.15`: sets a modest
  floor rate (~1 U/h for these TDIs) so the reservoir lasts all three days
  instead of being front-loaded. Larger theta_a front-loads insulin into day 1
  and leaves days 2-3 unopposed (worse TIR, worse rebound hyperglycaemia).
* `ec50_mg_dl = 144`, `hill_n = 0.588` (the lower bound): a very gentle,
  almost-linear glucose dependence. A steep switch (high n) concentrates
  insulin just above the threshold, and on the missed-lunch / large-dinner
  challenges that produced late post-meal hypoglycaemia (TBR70 up to 48 % in
  coarse candidates). The shallow sigmoid spends insulin smoothly, which
  generalises far better to unseen meal seeds.
* `tau_min = 0.84`: short filter, i.e. near-instant response to the filtered
  interstitial signal, so insulin already starts during the post-meal rise
  instead of lagging it.

## Selection procedure (see search.py, refine.py, search_log.json)
1. Coarse random search (240 points) in the shared box, scored on the ordinary
   variant only for throughput.
2. Re-scoring/top-14 and coordinate pattern search on all three training
   variants.
3. Unseen-seed robustness screen (seeds 6111006-6111009) — this eliminated the
   superficially best high-n candidate (TBR70 3.75 % on unseen seeds).
4. Multi-seed pattern refinement on 45 trajectories with tightened safety
   margins, then an independent fresh-seed check (6111010-6111013).

## Expected performance (fast RK4 trace, native-state start, day 1 omitted from TIR/TBR)
| set | mean TIR | max TBR70 | max TBR54 | min glucose |
|---|---|---|---|---|
| training seed, 3 variants (official metric) | 84.2 % | 0 % | 0 % | 71.5 mg/dL |
| 4 unseen seeds, 36 trajectories | 91.1 % | 0 % | 0 % | 71.4 mg/dL |
| 5 seeds x 3 variants, 45 trajectories | 87.2 % | 0 % | 0 % | 71.2 mg/dL |

## Safety reasoning (benchmark-only, not clinical advice)
The gate is binary (any trajectory with TBR70>4 %, TBR54>1 % or any minute
<40 mg/dL => zero). Across 81 trajectories from 5+4 meal seeds and all three
challenge variants the design never dropped below 71 mg/dL and had exactly zero
minutes <70, i.e. a ~31 mg/dL margin to the hard floor and a full 4-point margin
on TBR70 — chosen deliberately because evaluation uses fresh meal seeds and the
slow dopamine/insulin dynamics make near-threshold designs unstable. Insulin
delivery stays inside the box in `/task/instance.json` and the material/load
constraints of the synthetic subrange; no individual coefficients, boluses or
custom controller are used.
