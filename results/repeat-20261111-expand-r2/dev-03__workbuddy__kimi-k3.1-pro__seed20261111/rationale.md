# dev-03 formulation rationale

## Selected law

The submission is a cohort-shared **responsive** formulation with
`theta_a = 0.0002671016895883924`, `relative_leak = 0.9331847500032852`,
`ec50_mg_dl = 95.28590343404757`, `hill_n = 8`, `tau_min = 1.649913120580233`,
and `theta_L = 2.969955476968873`. Native TDI supplies each patient's amplitude
and reservoir scaling. There are no meal boluses, patient-specific fitted
coefficients, or online control additions.

The low EC50 and steep Hill response sharply reduce release as glucose falls,
while the relative leak maintains enough delivery between meals to avoid severe
hyperglycemia. The short filter time follows interstitial glucose closely.
These choices produced a useful tradeoff between the unusually sensitive child
#001 trajectory and the higher postprandial glucose of child #003. The roughly
3-TDI reservoir did not need to be sacrificed to obtain safety.

## Search and safety treatment

I first tested constant and responsive grids. Large initial amplitudes caused
unstable or profoundly hypoglycemic trajectories and were rejected. I then ran
seeded random sampling and evolutionary refinement around the feasible
responsive basin, followed by one-coordinate scans. The search objective was
mean post-warmup TIR minus penalties beginning at only 0.5% TBR70, any TBR54,
and minimum glucose below 58 mg/dL. This deliberately discourages selecting a
point immediately adjacent to a zero-scoring constraint. Shape parameters were
always clipped to the supplied bounds.

Broad search used training meal seed 6111003 and additional seed 712007;
refinement and candidate comparison used disjoint scenario seeds including
812011, 912017, and 1012019. All ordinary, day-2 missed-lunch, and day-2
50%-larger-dinner variants were included. The steeper candidates above `n=8`
increased hypoglycemia in the stress screen; `n=8` was selected because it had
zero measured TBR and a wider minimum-glucose margin.

## Observed checks (fast public integrator)

| Scenario set | Trajectories | Mean TIR (%) | Max TBR70 (%) | Max TBR54 (%) | Minimum glucose (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Given training seed, all variants | 9 | 77.546 | 0.000 | 0.000 | 70.907 |
| Seeds 812011 and 1012019, all variants | 18 | 85.758 | 0.000 | 0.000 | 70.491 |

A separate **native dopri5** check on child #001, seed 912017, large dinner gave
77.292% TIR, zero TBR70/TBR54, and full-horizon minimum 70.287 mg/dL. This close
agreement is only a numerical check, not a guarantee for unseen meals. Fresh
scenarios can still expose tails not represented in these finite tests, so the
selection favors the zero-TBR, higher-minimum candidate over nominally similar
candidates with incipient TBR70.

This is solely a simulation-benchmark design, not a clinical recommendation.
