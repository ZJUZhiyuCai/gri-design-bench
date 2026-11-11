# GRI static formulation design — instance dev-02

**Submitted design** (`design.json`): responsive mode,
`theta_a=0.00028`, `relative_leak=1.15`, `ec50_mg_dl=135`, `hill_n=2.5`,
`tau_min=6`, `theta_L=3.8` (all cohort-shared, inside every instance bound).

## What the mechanism actually is here
Rate = `theta_a*TDI*(relative_leak + Hill(mid-filtered interstitial glucose))`, capped by a
finite reservoir of `theta_L*TDI` units, i.e. the formulation is *basal-dominant with a
smooth, low-gain glucose-dependent boost*. For this design the delivered rate spans
~0.00032 TDI/min (glucose well below 135 mg/dL) to ~0.00060 TDI/min (well above), with
the reservoir (3.8*TDI over 3 days) never binding in the delivered range, so the
end-of-horizon behaviour is not clipped.

## How it was chosen (diagnostics, fast RK4, warm-up day excluded from TIR/TBR)
1. **Reference sweep (constant mode).** `theta_c=0.00040/0.00050` gives mean TIR 41/74.6 with
   minimum glucose 102/72; `0.00055` already reaches 58.5 mg/dL and `0.0008` 5.9 mg/dL.
   So the useful basal band is narrow, centred near `0.0005*TDI` U/min.
2. **Broad random search + hill climb** over the responsive shape (176+ evaluations on the
   cached training seed x 3 variants) found a training-optimum
   `[0.000232, 1.56, 126, 7.6, 1.6, 3.85]` with TIR 84.0 and min 71.5 — apparently excellent.
3. **Robustness gate on fresh meal seeds.** Re-evaluated on four RandomScenario seeds the
   training optimum collapsed to max-trajectory TBR70 = **9.3%** (a hard zero under the
   scoring rule), even though its mean TIR stayed 76. High Hill gain (`n=7.6`) on a ~1.6 min
   filter makes delivery swing hard; with the ~30-60 min insulin-action delay this rings and
   the low-meal seeds dip under 70. This is the central lesson of the instance: mean TIR on
   one meal seed is a bad objective when one trajectory can void everything.
4. **De-tuned, low-sensitivity family.** Lowering gain (`hill_n` 2.5), moving the midpoint to
   135 mg/dL, lengthening the filter to 6 min and raising the leak so the floor is a genuine
   basal rate removes the ringing. On the robustness set (training seed + 2 fresh seeds) this
   design scores **mean TIR 70.0%, max-trajectory TBR70 = 0%, TBR54 = 0%, minimum glucose
   74.3 mg/dL**, and the more aggressive sibling (`a=0.0003, leak=1.0, ec50=150, n=3.5`)
   scores 65.3 with min 77.5 — consistently safe and only mildly worse.

## Why this is the right trade
* The pass/fail constraint (`TBR70<=4%`, `TBR54<=1%`, any full-horizon minute `>=40 mg/dL`)
  is per trajectory, so the expected TIR must be sacrificed for margin: minimum glucose sits
  ~34 mg/dL above the floor and no trajectory reaches 70 mg/dL at all, on both the training
  and unseen meal seeds.
* Low gain + substantial leak behaves like a well-tuned basal dose whose only glucose
  dependence is a gentle brake below ~135 mg/dL and a gentle boost above; it cannot oscillate
  into sustained hypoglycaemia, and the explicit `relative_leak` floor keeps the day-1
  transient (before any meals are learned) from under-delivering.
* `theta_L=3.8` was kept high so the reservoir cap is inactive (it only protects against
  unbounded accumulation); the delivered basal-equivalent dose stays inside the band where
  the constant-mode sweep showed no hypo.
* Sensitivity was checked, not assumed: trained-seed-only optimum was rejected purely because
  of its fresh-seed TBR, and the surviving family is flat in TIR w.r.t. modest parameter moves.

## Caveats
Evaluated with the public fast RK4 integrator (`gri_bench.api.Experiment`); the trusted
verifier uses native simglucose dopri5, which is a tighter solver, and the ~34 mg/dL
minimum-glucose margin is far larger than observed integrator differences. Fresh evaluation
seeds change meal sizes only; because the dose is glucose-feedback driven rather than
schedule-driven, meal-size variation is absorbed by the Hill term rather than by blind
basal over-dosing. This is a simulation-benchmark result, not clinical guidance.
