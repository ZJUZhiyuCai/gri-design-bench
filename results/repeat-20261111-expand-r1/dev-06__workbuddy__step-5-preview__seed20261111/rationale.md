# GRI static formulation rationale (dev-06)

Placeholder initial rationale; refined after the search below.

## Design
Responsive mode. Rate = theta_a * TDI * (relative_leak + Hill(filtered IG)),
total insulin capped at theta_L * TDI over the three simulated days.

## Why responsive
A single static basal profile cannot simultaneously survive the day-2 missed
lunch (no carbohydrate, unchanged basal -> hypoglycaemia) and the 50% larger
dinner (more carbohydrate, unchanged basal -> hyperglycaemia).  The responsive
term adds insulin when filtered interstitial glucose rises, which is exactly
the perturbation both challenges introduce, while the leak term supplies the
fasting baseline.  The finite reservoir (theta_L * TDI) is a second, coarse
safety net against stacking.
