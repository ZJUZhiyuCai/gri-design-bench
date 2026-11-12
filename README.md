# GRI Design Bench

English · [简体中文](README.zh-CN.md)

GRI Design Bench evaluates how well AI agents design glucose-responsive insulin (GRI) formulations under a fixed compute budget. Each task asks an agent to choose one static formulation for three virtual patients, search with a public simulator, and submit a design for independent evaluation on fresh meal scenarios.

Version 0.1.1 contains **6 development cases and 6 sealed cases**, built from public virtual-patient physiology and synthetic material constraints. Development inputs are public; complete sealed inputs are held by the maintainer.

## The scientific problem

Insulin helps move glucose from the blood into cells. In type 1 diabetes, the body produces little or no insulin: too little replacement insulin leaves glucose high, while too much can drive it dangerously low. This creates a design problem when meals and insulin needs vary. [NIDDK explains the underlying biology](https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-1-diabetes).

Here, a glucose-responsive formulation is a finite insulin reservoir with a release mechanism that responds to the surrounding glucose concentration. Think of a valve whose opening depends on glucose: it releases more as glucose rises and less as glucose falls, subject to leakage, delay and the remaining supply. **The formulation parameters stay fixed; the release rate changes over time.** The agent chooses those parameters before evaluation.

For a responsive design, six parameters define the [release model](src/gri_bench/release.py):

| Design choice | What it controls |
|---|---|
| Release scale (`theta_a`) | The overall amount released per unit time |
| Basal leakage (`relative_leak`) | Release that persists even when the glucose-dependent response is small |
| Response midpoint (`ec50_mg_dl`) | The glucose concentration at which the responsive component reaches half its maximum |
| Response steepness (`hill_n`) | How sharply release switches from a weak to a strong response |
| Response delay (`tau_min`) | How quickly the formulation's internal glucose signal follows changes in surrounding glucose |
| Reservoir size (`theta_L`) | The total available insulin; release stops when it runs out |

A large dinner challenges the formulation to supply enough insulin; a missed lunch tests whether it releases too much when demand falls. Increasing release can improve early glucose control while raising low-glucose risk or exhausting the reservoir sooner. One shared design must work across three patients with different physiology. The task is therefore a constrained search for a useful balance across patients, meals and time.

The historical release-curve fit used data from [Xu et al.'s membrane-coated insulin crystals](https://www.nature.com/articles/s41565-025-01860-0). This benchmark abstracts that background into a glucose-only release model and an expanded parameter search space; [bound provenance](docs/BOUND_PROVENANCE.md) explains the construction. Agents optimize a simulated release behavior, with material synthesis left to subsequent experimental work.

## Results

The current comparison contains **9 model routes and 324 trials**: 12 cases × 3 repetitions per model. The first batch tested GPT, DeepSeek and GLM; the expansion added six open-weight model families under the same task, prompts and configured budgets. The table combines these two batches on the same six sealed cases, giving 18 attempts per model.

Time in range (TIR) is the percentage of evaluated time with glucose at 70–180 mg/dL. A design's `safe_tir` equals its mean TIR if every safety check passes, and zero otherwise. Ranks prioritize feasible attempts, then mean `safe_tir`; all attempts remain in the average. **SD is the sample standard deviation of the three round means.**

| Rank | Model | Batch | Feasible /18 | Mean safe TIR (%) ± SD |
|---:|---|---|---:|---:|
| 1 | GPT-6.1 Sol | Earlier three | 18/18 | 75.06 ± 0.63 |
| 2 | DeepSeek V4.1 Flash 1017 | Earlier three | 17/18 | 62.97 ± 7.40 |
| 3 | Kimi-K3.1-Pro | Added six | 15/18 | 54.31 ± 14.86 |
| 4 | Qwen3.8-27B | Added six | 10/18 | 24.17 ± 9.07 |
| 5 | GLM-5.3 | Earlier three | 9/18 | 23.40 ± 18.22 |
| 6 | MiniMax-M3.1-Flash | Added six | 3/18 | 10.17 ± 9.09 |
| 7 | Step-5-Preview | Added six | 3/18 | 8.40 ± 7.29 |
| 8 | MiMo-V2.6-Pro | Added six | 2/18 | 3.99 ± 5.18 |
| 9 | Intern-S2 | Added six | 1/18 | 4.25 ± 7.36 |

GPT produced feasible designs in all 18 sealed attempts. Among the six added models, Kimi ranked first and Qwen second in every round, while their round means ranged from 42.57–71.02 and 14.20–31.94 respectively. The other four models changed rank across rounds.

Failure categories reveal different bottlenecks. Kimi submitted 18 valid designs, of which 3 failed the safety checks; Qwen had 1 submission failure and 7 safety failures. MiniMax had 14 submission failures out of 18 attempts. For Kimi and Qwen, the results expose difficulty satisfying the physiological constraints; much of MiniMax's measured loss occurs before a design reaches simulation. The mean score therefore combines design quality with reliable execution of the task.

![Quality and feasibility across nine model routes](results/expansion-2026-11-11/comparison.png)

Thirteen of the 216 expansion attempts exceeded a recorded resource limit. The [strict-resource analysis](results/expansion-2026-11-11/README.md#resource-limit-sensitivity) assigns zero to each: the aggregate sealed ranking stays the same, while Intern's feasible count falls to 0/18. The table above retains the original native scores.

These results measure the routed agent workflow, including submission and API failures, on six fixed sealed cases already used in earlier trials. Model names identify requested Magpie routes; the actual upstream checkpoints remain unverified. The [full report](results/expansion-2026-11-11/README.md) includes per-round rankings, failure counts, resource use and [CSV](results/expansion-2026-11-11/leaderboard.csv)/[JSON](results/expansion-2026-11-11/summary.json) data.

## Task and scoring

Agents receive a three-patient cohort, native total daily insulin doses (TDI), material and reservoir bounds, and a training meal seed with ordinary, missed-lunch and large-dinner variants. They may use the public simulator to generate additional training scenarios within the compute budget.

The submission contains `design.json`, `search.py` and `rationale.md`. A design specifies a fixed glucose-responsive parameter vector or a constant release rate, shared across patients with dose amplitude and reservoir scaled by each patient's TDI. The permitted design space is static; real-time controllers, meal boluses and physiology edits fall outside it.

During a trial, the agent can read simulator code, write a search program, test candidates and inspect their glucose outcomes. It must allocate its compute budget between exploration, validation and saving the final design. The verifier then evaluates `design.json` over **18 three-day trajectories**: 3 patients × 2 evaluation seeds × 3 meal variants. Each trajectory is one patient's glucose history under one meal scenario. Fresh evaluation seeds test how well the chosen design handles meals beyond its training examples. Search code and rationale provide audit evidence; scores come from the independently simulated trajectories.

A design is feasible when every trajectory meets all three safety criteria:

- Time below 70 mg/dL is at most 4%.
- Time below 54 mg/dL is at most 1%.
- Glucose stays at or above 40 mg/dL throughout the simulation, including the first-day warmup.

TIR and time-below-range metrics exclude the warmup day, leaving 48 scored hours per trajectory. A raw TIR of 75% corresponds to 36 of those hours in range. Consider two hypothetical designs: one has an average TIR of 85% but lets one patient's glucose fall to 35 mg/dL, so its `safe_tir` is zero; another averages 75% and passes every safety check, so it scores 75. Requiring every trajectory to pass prevents a good cohort average from concealing a severe failure for one patient. The [task contract](contract/contract.json), [model amendment](contract/amendment-001-models.json) and [interaction amendment](contract/amendment-002-interaction-budget.json) define the protocol.

Each attempt has the following budget:

| Resource | Limit |
|---|---|
| Compute | 1 CPU, 2 GiB memory, 30 cumulative CPU seconds after JIT warmup |
| Elapsed time | 90 cumulative tool seconds; 360 seconds overall, including API waits |
| Model calls | 12 calls; up to 6,000 completion tokens per call and 18,000 per attempt |

Token accounting reserves each request's output allowance, including failed requests, and releases unused tokens only after a valid successful usage report. Trials use temperature zero and provider-default reasoning settings. CPU-limited comparisons require a common machine; the published runs used Linux/arm64 on an Apple M5 host.

Three fixed baselines show what conventional search achieves under the same CPU cap. The constant-rate grid tests a simple release schedule; Sobol search spreads candidates across the six-dimensional responsive design space; differential evolution uses previous candidates to guide further search. Their [single-run sealed scores](results/expansion-2026-11-11/README.md#fixed-baseline-reference) are 58.26, 44.93 and 54.39 respectively, each with 5/6 feasible cases.

## Run a development case

Use Python 3.12 and Docker with cgroup v2. The public repository includes all six development cases and their evaluation inputs. Reproducing sealed trials requires the private inputs held by the maintainer.

Install the locked environment and build the trial image:

```bash
git clone https://github.com/ZJUZhiyuCai/gri-design-bench.git
cd gri-design-bench
python3.12 -m venv .venv
.venv/bin/python -m pip install setuptools==80.10.2 wheel==0.48.0
.venv/bin/python -m pip install --no-build-isolation -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip install pytest==9.2.0
.venv/bin/python -m pytest -q
docker --context default build -t gri-bench:0.1.1 .
```

Run differential evolution on `dev-01`, then independently evaluate the saved design:

```bash
.venv/bin/python -m gri_bench.runner --case dev-01 \
  --method differential_evolution --context default --tag my-run

.venv/bin/python -m gri_bench.evaluate \
  private/runs/my-run/dev-01__differential_evolution__seed20261111 \
  --export results/my-run
```

To test an agent, configure an OpenAI-compatible endpoint and use the token-accounting runner:

```bash
export GRI_MODEL_BASE_URL=http://127.0.0.1:3425/v1
# Set GRI_MODEL_API_KEY if your endpoint requires authentication.
.venv/bin/python -m gri_bench.repeat_runner --case dev-01 \
  --model YOUR_ROUTE --context default --tag my-agent
```

Replace `YOUR_ROUTE` with the endpoint's model identifier and `default` with your Docker context. Credentials stay on the host. Trial containers run without network access, and archived agent code should be executed inside this sandbox.

## Evidence and project history

The [expansion audit](results/expansion-2026-11-11/audit.json) independently recomputed 2,016 native trajectories from 112 valid designs and verified all 1,608 API request reservations. All 799 earlier result files retain their original hashes. The public test suite contains 39 tests covering physiology, scoring, submission validation, budget accounting and result analysis.

Development exports include designs, transcripts and trajectories. Sealed exports contain aggregate scores and hashes of private evidence. The [validation record](docs/VALIDATION.md) documents sandbox checks, privacy checks, protocol freezes and result preservation.

| Record | Contents |
|---|---|
| [Nine-model expansion](results/expansion-2026-11-11/README.md) | Current comparison, three-round variability, failures and resource sensitivity |
| [Earlier three-model repetitions](results/repetitions-2026-11-11/README.md) | 108 trials under corrected token accounting |
| [Original pilot](results/pilot-v2/README.md) | Archived model and baseline results |
| [GLM route diagnosis](docs/GLM_502_DIAGNOSIS.md) | Output-limit exhaustion and omitted failed-request tokens in the original runner |
| [Expansion protocol](docs/MODEL_EXPANSION_2026_11_11.md) | Model selection, fixed budgets and the plan published before the 216 trials |
| [Added-model registry](experiments/expansion-2026-11-11/models.json) | Exact routes, public weight references and licenses for the six added models |
| [Material-bound provenance](docs/BOUND_PROVENANCE.md) | Source and construction of the synthetic design constraints |

The original GLM pilot exceeded its nominal token allowance in 10/12 trials because failed-request usage was omitted. Those results remain archived separately; the current comparison uses the corrected accounting profile.

Physiology derives from [simglucose 0.2.11](https://github.com/jxx123/simglucose). Numba RK4 accelerates search, and the native dopri5 verifier checks submissions. Benchmark code is released under the [MIT license](LICENSE); dependency attribution appears in [third-party notices](THIRD_PARTY_NOTICES.md).
