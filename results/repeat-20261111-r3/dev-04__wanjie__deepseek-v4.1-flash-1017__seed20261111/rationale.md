# GRI static formulation — dev-04

**Design (responsive):**
theta_a = 5.2e-4, relative_leak = 1.15, ec50 = 320.0 mg/dL, hill_n = 20.0,
tau_min = 2.0, theta_L = 1.25 (reservoir = full 1.25 x native TDI).

## Structure of the problem
The finite reservoir makes the design a *budget-allocation* problem, not a dosing
problem: at most `theta_L*TDI` units exist for the whole 3 days (~0.42 x TDI/day at
theta_L=1.25), i.e. roughly basal-only coverage. Because amplitude is
`theta_a*TDI`, the offered rate auto-scales with each patient's insulin
requirement, so a single shared coefficient set is defensible.

Two qualitative regimes were measured explicitly:
* **Uniform spend** (high `relative_leak`, small `theta_a`): the reservoir is spread
  flat over 72 h. adult#005 does well (~30-45 % TIR) but adult#004/006 sit at 0 %
  TIR - their amplitude-scaled rate is far too small to ever pull them into band.
* **Sharp switch** (large `hill_n`, `ec50` above the band, small floor): insulin is
  released almost only during hyperglycaemia, so the scarce budget is spent where
  it lowers glucose and is throttled automatically once glucose returns towards
  the band. This equalises performance across the cohort (~20-30 % TIR each) and
  was clearly superior (27 % vs 11-22 % mean TIR).

## Choices
* `ec50 = 320 mg/dL` with `hill_n = 20.0`: an almost binary on/off threshold placed
  well above 180 so the controller never "chases" the target band and burns budget
  while already in range.
* `relative_leak = 1.15`: enough floor to keep a basal-like trickle (P(<180) low,
  never hypoglycaemic), while the on-state is only ~1.9x the floor, limiting waste.
* `tau_min = 2 min`: a light filter; shorter values barely changed performance, and
  a 2-min lag suppresses pure noise without delaying the response.
* `theta_a = 5.2e-4`: sets the on-state rate at ~1.9 * 5.09e-4 * TDI U/min, which
  empties the reservoir over roughly the horizon while still allowing early
  correction of severe hyperglycaemia. The submitted values are the rounded, cleaned
  neighbours of the ES incumbent (5.09e-4 / 323 / 20.6), re-verified on all three seeds:
  mean TIR 27.5 %, min 72.4 mg/dL.
* `theta_L = 1.25` (upper bound): every extra unit of budget raised TIR monotonically
  and never produced any TBR70>0 in any trajectory.

## Safety
Across 3 meal seeds x 3 patients x 3 variants (27 trajectories) the design gives
**zero** minutes below 70 mg/dL (TBR70 = TBR54 = 0 %), max-TBR constraints satisfied,
and a worst-case minimum plasma glucose of 72.4 mg/dL - a 32 mg/dL margin over the
40 mg/dL disqualification threshold. Because the responsive form cannot deliver
more than `theta_a*(leak+1)*TDI` and the reservoir is finite, the failure mode is
hyperglycaemia, not hypoglycaemia; the verified margin reflects that asymmetry.

## Method
`search.py`: (1) log-uniform random population + structured seeds, (2) a (6+1)
evolution strategy on normalised log parameters (~175 fast RK4 evaluations, one
3-patient x 3-variant evaluation per candidate), scored by mean post-warmup TIR with
a hard feasibility gate plus a minimum-glucose safety penalty, (3) re-scoring of the
top candidates on two additional unseen meal seeds (6111005, 6111006) and selection
by worst-seed TIR to avoid seed overfitting. This simulation benchmark is not a
clinical recommendation.
