# GRI Design Bench v0.2 protocol

An agent designs one passive insulin release formulation for three known virtual patients. The simulator runs for three days with a finite reservoir and fixed formulation parameters. The patient profiles, dose scaling, release equations and RK4 search interface come from v0.1.1. The public development instances retain their cohort and material envelopes and use two training seeds.

## Submission and scoring

The host exposes two tools. `shell` runs code in a networkless Linux container. `submit_design` validates the mode, exact parameter names and numerical bounds, then atomically stores the design on the host. The latest accepted receipt before the deadline determines the candidate. Search code and rationale are optional audit files. The verifier reads the saved design as data and never runs submitted code.

Independent native dopri5 evaluation uses 16 evaluation seeds, three patients and three variants per seed. This yields 144 trajectories for a design. The variants are ordinary meals, a missed lunch and a larger dinner. Training and evaluation use disjoint seeds. Time in range (TIR) counts the percentage of time at 70–180 mg/dL on days 2 and 3.

Each trajectory must have at most 4% of time below 70 mg/dL and at most 1% below 54 mg/dL on days 2 and 3. Minute-level glucose must remain at or above 40 mg/dL over all three days. If all checks pass, the score is the mean TIR across trajectories. Missing or invalid designs, failed simulations, failed safety checks and resource violations score zero. The leaderboard averages every registered attempt. The report gives valid submissions, safety passes, and the gain in percentage points over the constant-release baseline on the same cases.

## Trial budget

The container has one CPU and 2 GiB memory. Setup and simulator warmup precede timing. Up to 30 cumulative cgroup CPU seconds and 90 cumulative tool seconds are available for shell work. The host pauses the container between shell operations and reserves time for stopping it. The 360-second submission deadline starts after setup and includes API waits and waits for an active sandbox. The host records API, tool, snapshot and cleanup time separately.

There are at most 12 model calls. Each request reserves up to 6,000 completion tokens from a trial total of 18,000, including reasoning tokens as reported by the route. Valid usage reports release the unused part of successful reservations. Failed requests and responses with unknown usage keep the reserve. A connection failure before establishment, an HTTP failure and a response timeout each receive their own recorded category. Two API or response-protocol errors end the trial.

All routes receive temperature 0 and a request for low reasoning effort. The routes determine how those settings are applied. When a response has no usable tool call and no design has been accepted, the host can send one corrective turn within the remaining budget. It ignores tool calls from truncated responses. Shell compute can end before the model's deadline, leaving time to call `submit_design`.

## Controls and held-out cases

Both competitive baselines use the same sandbox limits as the agents. The constant baseline searches the rate and reservoir size. The responsive baseline searches all six parameters. Both optimize training TIR with a margin around the safety thresholds. A separate calibration advances the same responsive optimizer through 30, 300 and 3,000 CPU seconds on the host. A refinement step searches around these checkpoints on 16 additional training seeds and verifies the selected design on the development evaluation panel. This provides a best-known search reference under a larger compute budget.

The original prompt example and a zero-release design serve as fixed controls. The 64-seed sensitivity study selects representative trajectories and cases close to safety thresholds for native checks. The pilot uses a separate, public set of 16 seeds per case. The [registered seed calibration](../../contract/v0.2/seed-calibration.json) explains the panel size.

The [development plan](../../contract/v0.2/development-plan.json) registers three routes, six cases and three repetitions, with the model order rotating by round and case. The sealed generator samples fresh triples from the public virtual patient pool, stratifies by age group and cycles through the development material envelopes. The maintainer stores the actual task files and evaluation seeds privately and publishes salted SHA-256 commitments before running the sealed matrix.

Reports pair methods within each case and resample cases to quantify uncertainty. Repetitions describe variation across runs on the same case. The per-attempt export records the routed model labels, submission outcome, budget ledger and evidence hashes. For public development cases it also includes the design. Sealed evaluation inputs and model transcripts remain private.

The calibration entry point is [calibrate_v02.py](../../scripts/calibrate_v02.py). It records the CPU milestones and their designs. [check_v02_scenarios.py](../../scripts/check_v02_scenarios.py) measures sensitivity to the evaluation panel. [refine_v02_reference.py](../../scripts/refine_v02_reference.py) selects the reference on its additional training seeds and verifies it on the public panel.
