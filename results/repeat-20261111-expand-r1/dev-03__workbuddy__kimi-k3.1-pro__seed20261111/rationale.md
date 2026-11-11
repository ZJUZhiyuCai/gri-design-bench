# Rationale: shared responsive GRI formulation (dev-03)

## Design choice

A responsive finite-reservoir formulation was selected. Its rate is scaled by
native TDI and combines a moderate basal leak with a sigmoidal response to
filtered interstitial glucose. The selected Hill midpoint is about 215 mg/dL,
with slope 3.43 and a relatively slow 14.90-minute filter. This gives sustained
insulin action after meals without an aggressive low-glucose response. The load
is 1.9174 times TDI, and all six parameters are shared by all three patients.

## Search and selection

I used fixed-seed Latin-hypercube searches with the supplied `Experiment` API:
first a broad range, then two narrower ranges around promising high-TIR shapes.
The objective combined mean post-warmup TIR with penalties for TBR70 above 2%,
any TBR54, and low minimum glucose. I retained the exact benchmark safety rules
when accepting finalists. Selection was not based on training alone: finalists
were re-evaluated on meal seeds 7111003, 8111003, and 9111003, covering ordinary,
missed-lunch, and large-dinner variants for every patient.

The selected candidate's supplied-RK4 results were:

| scenario set | mean TIR | maximum trajectory TBR70 | maximum TBR54 | full-horizon minimum |
|---|---:|---:|---:|---:|
| training seed 6111003 | 70.3935% | 0% | 0% | 72.8691 mg/dL |
| three fresh validation seeds | 70.1003% | 0% | 0% | 73.1105 mg/dL |

Thus all observed patient/scenario trajectories were feasible, with substantial
margin above the 40 mg/dL hard floor. These fresh-seed checks are empirical
robustness evidence, not a guarantee for every possible held-out meal draw.
The final verifier may use native dopri5, so the glucose margin is preferable to
choosing a more aggressive candidate whose TIR depended on borderline TBR.

`search.py` records the deterministic search procedure. `design.json` was
checkpointed atomically and is the sole artifact intended to set the simulation.
