# GRI static formulation rationale (instance dev-06)

Patients: child#004, child#005, child#006 (shared coefficients, responsive mode).
Objective: maximise mean post-warmup TIR on fresh meal seeds under a hard safety
contract (TBR70 <= 4%, TBR54 <= 1%, full-horizon min glucose >= 40 mg/dL).

Approach: safety-first offline search with the fast RK4 evaluator.
1. Coarse grid over (theta_a, relative_leak, ec50, hill_n, tau, theta_L),
   enforcing the safety contract on every training trajectory.
2. Greedy coordinate descent from the best feasible grid point.
3. Robustness confirmation on fresh meal seeds (never used for fitting the
   ranking beyond a final accept/reject), then write `design.json`.

Rationale for shape: a small baseline leak keeps overnight/fasting delivery near
basal (hypo protection, especially on the day-2 missed-lunch challenge), while a
Hill term centred near euglycemia adds meal-time augmentation so postprandial
excursions stay nearer [70, 180]. The reservoir (theta_L) is sized so the pump
does not run dry late in day 3.

(This file is updated with the final search results at submission time.)
