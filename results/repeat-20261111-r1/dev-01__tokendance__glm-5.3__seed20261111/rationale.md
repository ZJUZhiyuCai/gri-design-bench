# GRI static formulation — dev-01 (initial draft)
Goal: maximize post-warmup mean TIR [70,180] on fresh meal seeds for adult#001-003,
subject to TBR70<=4%, TBR54<=1%, min glucose>=40 (full 3 days).
Approach: responsive mode; rate = theta_a*TDI*(relative_leak + Hill(Gf)).
Use theta_L near 3-4 so the reservoir can cover ~3 days of needs; tune theta_a/leak
so fasting basal is close to native basal (u2ss*BW/6000) without going hypoglycemic,
and Hill params give postprandial boost. Search: coordinate descent with the fast
RK4 evaluator on the 3 training variants; robustness checked on extra seeds.
