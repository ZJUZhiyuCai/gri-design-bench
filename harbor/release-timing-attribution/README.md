# Release timing attribution

This local Harbor task reproduces a mechanistic counterfactual analysis. The scientific output is a complete set of matched replay results with daily insulin amounts, glucose metrics and paired effects. Its material provenance and research scope are documented in [Scientific scope](../../docs/SCIENTIFIC_SCOPE.md) and the [six-cohort study](../../results/timing-study-2026-11-13/README.md).

## Difficulty

The solver must recover the release history, preserve each day's dose, apply two distinct open-loop interventions, and compute physiological outcomes on the correct time windows. Pooling both evaluation days preserves the total dose while violating the daily match. In a local pilot on one fixed panel, agents also ran out of request budget before producing files, hit a runtime error in replay, or reversed the sign of a paired effect. A script can reproduce the sign error exactly. The pilot measured execution and reproducibility on the given workflow.

## Reference solution

`solution/solve.sh` copies the author implementation to `/app/output/reproduce.py` and runs it against the supplied panel. It computes the responsive history using the native solver and applies the transformed rates to the same physiological initial state. The alternate implementation obtains the responsive rates from RK4 and applies them with the native prescribed-rate simulator.

## Verification

The verifier reference is generated independently of `solution/` using the original `simglucose==0.2.11` patient RHS with dopri5. The agent receives the `dev-06` public-development configuration, a previously published high-budget design and two new meal seeds. The verifier checks all 54 arm/scenario rows, responsive rates, dose conservation, common warmup, exact intervention semantics, glucose outcomes and aggregate contrasts. Time fractions use an absolute tolerance of 0.11 percentage points, enough for one three-minute sample out of 960. Minimum glucose uses 0.02 mg/dL. Rate and dose checks allow floating-point error. Independent reference-generation code and input digests are captured under `authoring/` in the generated task.

The build copies only an allowlist of simulator code and the panel and schema into the agent environment. The separate verifier reads `results.json` as data, uses pytest, and emits CTRF. The replay command checks the original Harbor task digest, starts a fresh offline task container, uploads the archived script, and executes it. The same separate verifier grades the regenerated JSON. Full acceptance requires both verifier passes, a zero script exit code, and matching results. The comparison keys rows by scenario and arm, ignores JSON formatting and row order, and allows an absolute difference of `1e-10` for each numeric value. It records exact byte matches separately. The script size limit is 1 MiB and the JSON size limit is 16 MiB.

The original controls below used the JSON verifier. Their records identify the original task and inputs.

| Harbor control | Reward | Evidence |
|---|---:|---|
| Native responsive solver and prescribed-rate replay | 1 | Five pytest checks passed |
| RK4 responsive solver and native prescribed-rate replay | 1 | Five checks passed, all time-fraction metrics matched to floating-point precision |
| Empty submission | 0 | Required artifact missing |
| Uniform rate across both evaluation days | 0 | Daily dose and replay outcomes failed despite matching the total dose |

These trials ran in Harbor 0.25.0 and Linux arm64 Docker using a separate verifier. The RK4 variant differed from the native reference by at most (5.09\times10^{-5}) mg/dL on minimum plasma glucose and (5.80\times10^{-8}) U/min on release rate. The wrong-dose control changed one daily amount by 0.554 U while preserving three-day totals within (5\times10^{-13}) U. This checks the scientific constraint at the level of the individual day. [Trial results and hashes](../../results/timing-study-2026-11-13/harbor-verification.json)

## Local run

From the repository root, install the project and Harbor 0.25.0. Select a running Docker context. The generator builds a standalone task with separate agent and verifier images. Native reference generation can take several minutes. [Project installation](../../README.md#reproduce)

```bash
.venv/bin/python -I scripts/build_timing_harbor.py --output private/timing-reproduction-task
gri_docker_context=default
HARBOR_TELEMETRY=0 DOCKER_CONTEXT="$gri_docker_context" harbor run \
  -p private/timing-reproduction-task -a oracle -e docker -n 1 -k 1 -r 0 \
  -o private/timing-reproduction-jobs --job-name oracle &&
DOCKER_CONTEXT="$gri_docker_context" python scripts/check_timing_replay.py \
  --task private/timing-reproduction-task \
  --trial private/timing-reproduction-jobs/oracle/timing-reproduction-task__* \
  --output private/timing-reproduction-replay
```

Set `gri_docker_context` to the name of your Docker context. Run the replay command with Harbor's Python environment. For an agent run, pass its specific trial directory, containing `result.json`, `lock.json` and `artifacts/`. The output directory must be new. `comparison.json` records the two scientific verdicts, script and output hashes, execution times, and final status. The command exits 0 for full acceptance, 1 for a rejected or incomplete trial, or 2 for invalid inputs.

Use `-a nop` for the empty-submission control. To run the alternate RK4 solution on the full workflow, copy the generated task and set the default method in that copy's `solution/solve.py` to `rk4`. Set the default to `wrong` to check the effect of pooling the daily dose. Pass `--meal-seeds SEED1 SEED2` at build time to use a different two-seed panel. The default seeds reproduce the original public panel. Use `--reuse-reference` only with a matching panel and provenance.

Docker build may download pinned dependencies. The agent, replay and verifier run offline. The recorded local trials supplied cached, version-checked images via `--agent-base` and `--verifier-base`. The generator defaults to the pinned Python base and dependency lists.
