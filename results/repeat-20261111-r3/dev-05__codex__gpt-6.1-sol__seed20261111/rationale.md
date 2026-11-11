# Submitted formulation

Responsive release with shared coefficients: theta_a=0.00025, relative_leak=1.5, EC50=65.0 mg/dL, Hill exponent=8.0, filter time constant=0.05 min, reservoir multiplier=4.0. Every coefficient satisfies the instance bounds. Amplitude and finite reservoir scale only by the provided native TDI; no patient-specific fitting or boluses are used.

## Design choice

The minimum allowed leak gives the strongest permitted modulation relative to basal release. A low EC50 and moderate Hill exponent preserve release through the usual glucose range while reducing release as glucose approaches the hypoglycemic range. The small filter time constant avoids extra response delay on top of the interstitial and subcutaneous physiological delays. The reservoir is deliberately ample: the maximum normalized flux is 0.000625 per minute, so even continuous maximum release for 4320 minutes would consume only 2.7 TDI, below the 4 TDI load.

## Search and evidence

The search varied amplitude, EC50, and Hill slope over the known cohort, always resetting native physiological initial states. Broad scans used one-minute RK4 for speed; the final check uses the public default quarter-minute RK4. All minima include warmup; TIR and TBR omit the first day. Candidate selection required each trajectory to pass the benchmark safety limits, with an additional 2% maximum TBR70 selection margin during the last comparison.

The selected design achieved 89.75434% mean TIR across 80 fresh seeds (918200 through 918279), all three challenge variants and all three patients: 720 trajectories. Maximum TBR70 and TBR54 were both 0%; full-horizon minimum glucose was 70.83123 mg/dL. An independent earlier 13-seed set (training seed plus 734120 through 734131) gave 89.79968% mean TIR, 0% TBR70, 0% TBR54, and minimum 70.87066 mg/dL. These fresh sets were subsequently used for selection and are not held-out guarantees.

Increasing amplitude from 0.000250 to 0.000252 raised the 80-seed mean TIR only to 89.95501%, but increased worst-trajectory TBR70 to 2.60417%. The lower amplitude was retained to preserve a useful safety margin against new meals and integrator differences.

Final quarter-minute RK4 check, covering 162 trajectories on the 13 earlier seeds and five difficult fresh seeds: mean TIR 89.471451%; maximum TBR70 0.000000%; maximum TBR54 0.000000%; full-horizon minimum 70.831226 mg/dL. See final_validation.json for per-trajectory evidence.

Native dopri5 verification was not run within the compute budget. Training and fresh-seed observations cannot guarantee safety on the verifier's unseen meals. This is a simulation benchmark formulation, not a clinical recommendation.

## Reproduction

Run stages in order with OPENBLAS_NUM_THREADS=1: `python /work/output/search.py probe`, then `search`, `validate`, `refine`, `stress`, `final_tune`, and `finish`. The final selection uses the largest mean TIR among formulations passing the final 2% maximum-TBR70 selection margin on the 80-seed set. Atomic saves protect design checkpoints. Full results are retained in trials.jsonl, validation.json, refinement.json, stress.json, final_tuning.json, and final_validation.json.
