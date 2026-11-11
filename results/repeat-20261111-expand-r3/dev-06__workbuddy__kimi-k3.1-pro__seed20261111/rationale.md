# GRI static formulation design — dev-06

## Submitted formulation

The design is a responsive formulation with the six shared coefficients stored
in `design.json`. It uses a low relative leak near the permitted lower bound,
a Hill response centered near 204 mg/dL, a 7.38-minute glucose filter, and a
finite reservoir of approximately 1.60 times native TDI. Amplitude scales with
native TDI exactly as required; there are no patient-specific coefficients or
external meal boluses.

## Search and selection

`search.py` implements deterministic stratified global search followed by
shrinking local search. Candidate scoring prioritizes safety violations before
TIR. The audit workflow then runs `refine.py` and `validate.py`, which perform
fixed-seed local refinements on increasingly broad scenario sets. In particular,
selection was not based on the single training seed alone: the final incumbent
was selected using 45 trajectories (three patients, three challenge variants,
and five meal seeds). Improved designs were saved atomically.

The final five-seed local-selection evaluation reported mean TIR **46.12%**,
maximum trajectory TBR70 **1.67%**, maximum trajectory TBR54 **0%**, and minimum
full-horizon plasma glucose **69.60 mg/dL**. On the original nine-trajectory
training experiment, the submitted design reported mean TIR **47.47%**, TBR70
**0%**, TBR54 **0%**, and minimum glucose **74.83 mg/dL**. These are diagnostics
from the fast RK4 training API, not guarantees for unseen scenarios or the
native dopri5 verifier. The chosen safety margins were intended to reduce, but
cannot eliminate, held-out scenario risk.

This is solely a simulation-benchmark formulation and is not a clinical
recommendation.
