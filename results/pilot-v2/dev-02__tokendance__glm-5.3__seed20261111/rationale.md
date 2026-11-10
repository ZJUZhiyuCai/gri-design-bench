# GRI dev-02 design rationale (draft)

Instance dev-02: shared-coefficient responsive insulin shape for adolescent#001-003,
evaluated on 3-day simulations (1440 min warmup) with fresh meal seeds. Objective:
maximize mean post-warmup TIR in [70,180] mg/dL subject to hard safety gates
(TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40 mg/dL over full horizon, all
patient/scenario pairs). Search: random + coordinate refinement with penalty scoring,
validated on extra meal seeds. (Full rationale will be expanded after experiments.)
