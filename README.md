# GRI Design Bench

English · [简体中文](README.zh-CN.md)

GRI Design Bench uses glucose-responsive insulin (GRI) release in virtual patients to test whether an agent can run a controlled pharmaceutical simulation and produce results that an independent verifier can reproduce. The release-timing task asks how changing when insulin is released affects simulated glucose when each day's amount stays the same.

| Task or study | What it does | Trial status | Entry |
|---|---|---|---|
| Release-timing attribution | Build dose-matched controls and submit 54 result rows with a runnable script | Offline validation complete. Model retest paused. | [Harbor task](harbor/release-timing-attribution/README.md) |
| Timing study | Author-run dry experiment using the same controls on 216 paired scenarios | Author study complete | [Timing study](results/timing-study-2026-11-13/README.md) |
| v0.2 design task | Formulation search under a compute budget, scored on new meals | 9 routes, 324 attempts | [Nine-route report](results/v0.2/expansion-2026-11-13/README.md) |
| Material validation diagnostic | Which added measurement changes a go/no-go call on 24 simulated states | Baseline comparison complete | [Material validation](results/material-validation-2026-11-13/README.md) |

[Scientific scope](docs/SCIENTIFIC_SCOPE.md) · [Capabilities and research loop](docs/RESEARCH_LOOP.md) · [Material bounds](docs/BOUND_PROVENANCE.md)

## Why GRI comes first

Differences between responsive and steady release can arise from the amount of insulin delivered each day or its timing. In the simulator, we can keep the virtual patient, meals, initial state and each day's delivered amount fixed, then change the within-day release schedule.

GRI design has a precedent in pharmacokinetic modeling, and published in vitro measurements inform part of our release model. We chose it first because the daily dose constraint can be checked row by row. Paired results show where the timing effect appears or weakens and help identify assumptions to test in the next experiment. [Bakh et al. (2017)](https://pubmed.ncbi.nlm.nih.gov/28841775/) · [Xu et al. (2025)](https://pubmed.ncbi.nlm.nih.gov/40011600/)

A complementary prototype in the broader project uses plasma concentrations from a published growth-hormone patch study to infer effective timing and predict the held-out tails of the same three curves. That task tests inference from measurements. The GRI task tests whether an agent can implement a controlled comparison and reproduce its outcomes. [Han et al. (2025)](https://pubmed.ncbi.nlm.nih.gov/40181125/)

## Release-timing attribution

The task supplies a fixed formulation and three virtual patients from `dev-06`, two meal seeds, and three meal variants (ordinary meals, a missed lunch and a larger dinner). The agent runs three simulations per scenario.

1. Simulate the original responsive release trajectory.
2. Keep day 1 unchanged and redistribute each of days 2 and 3 uniformly within that day.
3. Keep day 1 unchanged and shift each of days 2 and 3 by 12 hours, wrapping within the day.

Both controls use the completed responsive release trace for a retrospective comparison. Day 1 serves as a common warm-up.

The agent writes `/app/output/results.json` with 54 rows (3 patients × 2 seeds × 3 meal variants × 3 arms). Each row includes the release trajectory, daily amounts, time in range (TIR, 70–180 mg/dL), time below 70 and 54 mg/dL, and minimum glucose. Time fractions use days 2–3. Minimum glucose uses all three days. The file also reports mean paired differences as responsive minus control. The agent submits the script that generated it as `/app/output/reproduce.py`. [Task instructions](harbor/release-timing-attribution/instruction.md)

A separate Docker verifier checks row coverage, release rates, per-day dose matching, the shared warm-up, control definitions, glucose metrics and paired differences. It uses a reference generated independently with the original `simglucose` physiology and native dopri5. Full acceptance requires the archived script to produce numerically matching results in a fresh offline task container and both outputs to pass the same scientific checks. [Local acceptance workflow](harbor/release-timing-attribution/README.md#local-run)

### Validation status

Offline validation used Harbor 0.25.0 and one fixed panel of 18 meal scenarios. The native solution and the RK4 release solver with native replay each passed all five checks on both runs and reproduced their own output byte for byte. Six controls were rejected.

| Rejected control | Check that caught it |
|---|---|
| Uniform release pooled across both evaluation days | Per-day dose and timing |
| Reversed paired effect | Signed paired difference, even when replay matched byte for byte |
| Empty submission | Required results |
| Missing script | Required replay script |
| Script that fails when rerun | Replay exit code |
| Script that produces a different valid result | Numerical agreement between the two outputs |

The original cross-day pooling control preserved the three-day total to floating-point precision and shifted one day's dose by 0.554 U. [Original verifier controls](results/timing-study-2026-11-13/harbor-verification.json)

The earlier model pilot used this same 18-scenario panel and exposed budget exhaustion, script errors, and reversed paired effects. On the updated task, the fixed script passed all five initial checks in three runs. The model retest was paused before the first model trial reached verification. Raw trial records are kept locally.

## Author-run timing study

The authors ran the same comparison on six fixed designs across the public development cohorts. The 216 paired meal scenarios reuse 18 virtual patients. The Harbor task uses its own smaller input panel.

Compared with dose-matched daily uniform release, the responsive arm had mean TIR **5.82 percentage points higher** and mean time below 70 mg/dL **3.74 points lower**. Cohort-level TIR gains ranged from 0.55 to 12.30 points. Some individual scenarios saw no gain.

[Plan](results/timing-study-2026-11-13/plan.json) · [Summary](results/timing-study-2026-11-13/summary.json) · [Per-scenario outcomes](results/timing-study-2026-11-13/outcomes.json)

### From output to paper evidence

| Paper element | What the artifacts provide |
|---|---|
| Methods | Run plan recorded before simulation, with the three arms, shared warm-up, per-day dose matching and analysis window |
| Main figure | Paired differences by cohort, recomputable from the per-scenario table |
| Supplement | The full per-scenario table, including scenarios without improvement, plus input and script versions |
| Conclusion | Limited to this simulator and these six fixed designs |

The acceptance workflow checks the submitted JSON and reruns the archived script. Researchers can review the code and provenance alongside the verified outputs. Measuring the effect on research workload requires timing preparation, review and corrections under matched inputs, simulation budgets and verification.

## v0.2 design task

[![v0.2 design task: glucose changes release from a fixed formulation. The agent tests and submits candidates. An independent verifier scores the final design on 144 trajectories.](docs/assets/benchmark-overview-v02-en.png)](docs/assets/benchmark-overview-v02-en.svg)

The agent receives three virtual patients, material bounds and two training meal seeds. It has 30 cumulative CPU seconds to search for a responsive or constant-rate formulation. The latest valid design accepted through `submit_design` is scored. The same parameters apply to all three patients, with release and reservoir scaled to each patient's reference daily insulin amount.

| Responsive parameter | What it controls |
|---|---|
| `theta_a` | Overall release scale |
| `relative_leak` | Basal release when the glucose response is weak |
| `ec50_mg_dl` | Glucose level at half of the maximum responsive component |
| `hill_n` | How sharply release increases around that midpoint |
| `tau_min` | How quickly the formulation responds to tissue glucose |
| `theta_L` | Total insulin available in the reservoir |

The verifier reruns 144 three-day trajectories (3 patients × 16 fresh meal seeds × 3 meal variants) with native dopri5. Every trajectory must meet all three simulated glucose limits.

- Time below 70 mg/dL is at most 4% on days 2–3.
- Time below 54 mg/dL is at most 1% on days 2–3.
- Minute-sampled glucose stays at or above 40 mg/dL across all three days.

A passing design scores its mean TIR on days 2–3. Missing or invalid submissions, failed simulations, glucose-limit failures and resource violations score zero. [v0.2 protocol](docs/v02/PROTOCOL.md) · [Release model](src/gri_bench/release.py)

Nine Magpie routes ran six development and six sealed cases three times each, for 324 attempts. The 24 fixed-optimizer baseline runs used the same search CPU budget. The sealed cases use new combinations from the same public pool of virtual patients and new meal scenarios. Each route has 18 sealed attempts.

| Route or baseline | Valid designs | Passes glucose limits | Mean score (%) |
|---|---:|---:|---:|
| GPT-6.1 Sol (highest) | 18/18 | 18/18 | 73.11 |
| Intern-S2 (lowest) | 3/18 | 2/18 | 8.20 |
| Responsive baseline | | | 58.03 |
| Constant baseline | | | 49.48 |

On the sealed set, pairwise agreement between round rankings ranged from 0.67 to 0.83 (Kendall's τ-b). Seven of 36 route pairs changed order at least once. The end-to-end score reflects tool use, search, budget management and submission quality. The full report shows development results and failure categories.

[Nine-route report and full table](results/v0.2/expansion-2026-11-13/README.md) · [Original three-route run](results/v0.2/sealed/README.md) · [Calibration](results/v0.2/calibration/README.md)

## Which additional evidence changes a decision?

This study asks which added measurement would change a go/no-go call on a candidate. It covers six cohorts with four simulated material states each, judged on an independent meal panel.

- Always verifying baseline leakage raised agreement with the reference decision from 22/24 to 24/24, recovering two missed states.
- Always verifying response delay stayed at 22/24.
- Choosing the measurement per case picked the same measurement on these inputs and matched the fixed leakage baseline.

The measurements were idealized simulator queries. The case-specific policy matched the fixed leakage policy. This study stopped at the baseline comparison. The next experiment prioritizes measured release at low glucose and the amount remaining in the reservoir. [Research loop](docs/RESEARCH_LOOP.md) · [Material validation study](results/material-validation-2026-11-13/README.md)

## Model sources and scope

- **Release model.** Part of the release shape comes from a historical fit to the in vitro curve of membrane-coated insulin crystals in Xu et al. Xu et al. studied a material that responds to glucose and β-hydroxybutyrate. The benchmark uses a glucose-only model with a finite reservoir, expanded fit bounds and synthetic dose and loading constraints. [Bound provenance](docs/BOUND_PROVENANCE.md)
- **Physiology.** The benchmark uses `simglucose 0.2.11`, an open-source research implementation with 30 virtual subjects, together with a custom release layer and a three-day multi-meal protocol. The physiological equations omit hypoglycemia counterregulation. [simglucose](https://github.com/jxx123/simglucose)
- **Regulatory precedent.** In 2008 the FDA accepted the original UVA/Padova type 1 diabetes simulator in lieu of animal trials for specific preclinical tests of artificial-pancreas closed-loop control strategies. The developers describe the validated and accepted setting as limited to a single meal. This project's three-day protocol supports model-specific conclusions. Clinical safety, efficacy and material feasibility require separate evidence. [Kovatchev et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC2681269/) · [Dalla Man et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4454102/)

## Reproduce

Set up the project from the repository root with Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install setuptools==80.10.2 wheel==0.48.0
.venv/bin/python -m pip install --no-build-isolation -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
```

Run the timing study in the Python environment and use a new output directory.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  .venv/bin/python -I scripts/run_timing_study.py --output private/my-timing-study
```

A v0.2 development case also needs `curl` and a running Docker context with cgroup v2. Set `gri_docker_context` to its name.

```bash
gri_docker_context=default
docker --context "$gri_docker_context" build -t gri-bench:0.1.1 .
docker --context "$gri_docker_context" build -f Dockerfile.v02 -t gri-bench:0.2.0 .
.venv/bin/python -m gri_bench.v02.matrix --context "$gri_docker_context" \
  --case dev-01 --output private/my-baseline
```

This runs the fixed responsive baseline without a model account. To run an agent on the same case, add `--model YOUR_ROUTE` and choose a new output directory. The runner uses `GRI_MODEL_BASE_URL` (default `http://127.0.0.1:3425/v1`) and the optional `GRI_MODEL_API_KEY`. Use a fresh output directory for each run. The directory stores the submission, trial record and native score.

Build and offline control instructions for the Harbor task are in [its README](harbor/release-timing-attribution/README.md).

[Development inputs](instances/dev/) · [Evaluation seeds](instances/v0.2/development-evaluation.json) · [Registered development plan](contract/v0.2/development-plan.json) · [Sealed commitments](contract/v0.2/sealed-manifest.json)

The v0.1.1 archive holds an earlier nine-route, 324-attempt comparison using its own protocol. [v0.1.1 archive](https://github.com/ZJUZhiyuCai/gri-design-bench/tree/31b8731f927691ccb4ed46064d3974dd5bf55373) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
