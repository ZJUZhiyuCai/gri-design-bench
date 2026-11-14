# Release timing attribution

This local Harbor task reproduces a mechanistic counterfactual analysis. The scientific output is a complete set of matched replay results with daily insulin amounts, glucose metrics and paired effects. Its material provenance and research scope are documented in [Scientific scope](../../docs/SCIENTIFIC_SCOPE.md) and the [six-cohort study](../../results/timing-study-2026-11-13/README.md).

## Difficulty

The solver must recover the release history, preserve each day's dose, apply two distinct open-loop interventions, and compute physiological outcomes on the correct time windows. Flattening over both evaluation days preserves the two-day dose while violating the daily match. This error is included as a control. The prescribed workflow makes this a reproducibility task. Its difficulty for frontier agents and its suitability for an official submission remain unmeasured.

## Reference solution

`solution/solve.sh` runs an author implementation against the public scenario panel. It computes the responsive history using the native solver and applies the transformed rates to the same physiological initial state. The alternate implementation obtains the responsive rates from RK4 and applies them with the native prescribed-rate simulator.

## Verification

The verifier reference is generated independently of `solution/` using the original `simglucose==0.2.11` patient RHS with dopri5. The agent receives the `dev-06` public-development configuration, a previously published high-budget design and two new meal seeds. The verifier checks all 54 arm/scenario rows, responsive rates, dose conservation, common warmup, exact intervention semantics, glucose outcomes and aggregate contrasts. Time fractions use an absolute tolerance of 0.11 percentage points, enough for one three-minute sample out of 960. Minimum glucose uses 0.02 mg/dL. Rate and dose checks allow floating-point error. Independent reference-generation code and input digests are captured under `authoring/` in the generated task.

The build copies only an allowlist of simulator code and the public panel and schema into the agent environment. The separate verifier reads `results.json` as data, uses pytest, and emits CTRF. The prototype uses offline local containers and a 900-second agent budget. For upstream review, use the current [Terminal-Bench-Science contribution guide](https://github.com/harbor-framework/terminal-bench-science/blob/0c224bf9349047c82ff8ff5fae62e12dca8e89ad/CONTRIBUTING.md) and [task rubric](https://github.com/harbor-framework/terminal-bench-science/blob/0c224bf9349047c82ff8ff5fae62e12dca8e89ad/rubrics/task-implementation.toml).

| Harbor control | Reward | Evidence |
|---|---:|---|
| Native responsive solver and prescribed-rate replay | 1 | Five pytest checks passed |
| RK4 responsive solver and native prescribed-rate replay | 1 | Five checks passed, all time-fraction metrics matched to floating-point precision |
| Empty submission | 0 | Required artifact missing |
| Uniform rate across both evaluation days | 0 | Daily dose and replay outcomes failed despite matching the total dose |

These trials ran in Harbor 0.25.0 and Linux arm64 Docker using a separate verifier. The RK4 variant differed from the native reference by at most (5.09\times10^{-5}) mg/dL on minimum plasma glucose and (5.80\times10^{-8}) U/min on release rate. The wrong-dose control changed one daily amount by 0.554 U while preserving three-day totals within (5\times10^{-13}) U. This checks the scientific constraint at the level of the individual day. [Trial results and hashes](../../results/timing-study-2026-11-13/harbor-verification.json)

## Local run

From the repository root, install the project using the [main README](../../README.md#reproduce). Install Harbor 0.25.0 and select a running Docker context. The generator builds a standalone task with separate agent and verifier images. Native reference generation can take several minutes.

```bash
.venv/bin/python -I scripts/build_timing_harbor.py --output private/timing-reproduction-task
gri_docker_context=default
HARBOR_TELEMETRY=0 DOCKER_CONTEXT="$gri_docker_context" harbor run \
  -p private/timing-reproduction-task -a oracle -e docker -n 1 -k 1 -r 0 \
  -o private/timing-reproduction-jobs --job-name oracle
```

Set `gri_docker_context` to your Docker context. Use `-a nop` and a separate job name for the empty-submission control. To reproduce the two other controls, copy the generated task into fresh directories. In their `solution/solve.sh`, pass `--method rk4` or `--method wrong` to the existing `solve.py`. The reference and verifier remain identical across controls. Docker build may download pinned dependencies. The trial and verifier run offline. A different local Docker context can be selected by setting `DOCKER_CONTEXT`.

The recorded local trials supplied cached, version-checked images via `--agent-base` and `--verifier-base`. The image digests are in the trial evidence. The build generator defaults to the pinned Python base and dependency lists.
