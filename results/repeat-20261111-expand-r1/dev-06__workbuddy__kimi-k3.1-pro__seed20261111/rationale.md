# Cohort-wide GRI formulation rationale

The selected responsive law uses one shared parameter vector and each patient's
native TDI only for the prescribed scaling. The amplitude, Hill midpoint and
steepness were screened on all three challenge variants, then compared on four
meal seeds. The finite reservoir is sized at `2*TDI`; observed runs exhausted it
before day 3, so increasing the load did not improve the result.

The minimum permitted relative leak was favored in screening because it avoids
unneeded low-glucose insulin delivery, while the Hill term supplies meal response.
A steep Hill response (`n=4`) and midpoint 140 mg/dL improved TIR without relying
on patient-specific tuning. The filter time of 5 min balances meal response and
post-meal hypoglycemia. Candidate selection imposed stricter internal checks than
the pass rule: maximum TBR70 <=2%, TBR54=0, and full-horizon minimum >=55 mg/dL.
The saved candidate's 36-trajectory multi-seed fast-RK4 check had mean TIR 52.36%,
zero maximum TBR70/TBR54, and minimum glucose 70.22 mg/dL. This is a simulation
benchmark design, not a clinical recommendation; fresh-seed safety is not assumed
from training performance.
