# GRI static formulation design (dev-04) - initial checkpoint

Placeholder checkpoint; see below for the search plan. Final numbers are filled in
after the search completes.

## Problem
Choose one shared set of six responsive coefficients so that a 3-day, three-patient
cohort simulation (adult#004/005/006) maximises mean time-in-range on NEW meal
scenarios while never violating the safety envelope.

## Approach
1. Random (log-uniform) exploration of the six-dimensional bounded box.
2. Multiplicative Gaussian local refinement around the best seeds.
3. Hard constraint: any candidate with per-trajectory TBR70 > 4%, TBR54 > 1% or a
   full-horizon minimum glucose < 40 mg/dL is discarded (infinite penalty).
4. Checkpointed atomically via a temp file + os.replace.
