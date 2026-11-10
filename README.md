# GRI Design Bench

A small benchmark of **who can design a better static glucose-responsive insulin formulation** under a fixed simulation and compute budget. Version 0.1.1 contains **6 development and 6 sealed instances**, one task family, three known virtual patients per instance. It measures design and optimization in a public simulator, with fresh meal scenarios at evaluation.

This is an engineering pilot. It does not establish clinical efficacy, safety in real patients, generalization to unseen patients, or a stable ranking of foundation models. The 30 simglucose profiles were public and used in preceding studies. Material subranges are synthetic benchmark constraints inside an intentionally expanded prescreen design envelope; they are not newly measured formulations or a demonstrated manufacturing-feasibility region. See [bound provenance](docs/BOUND_PROVENANCE.md).

## First pilot results

**36 formal agent trials + 36 baseline trials, all independently resimulated.** The six sealed cases give the following descriptive results, sorted by feasible-case rate and then mean safe TIR. A safety-gate failure contributes zero to the mean.

| Method / requested route | Feasible sealed cases | Mean safe TIR (%) |
|---|---:|---:|
| `codex/gpt-6.1-sol` | 6/6 | 75.06 |
| `wanjie/deepseek-v4.1-flash-1017` | 6/6 | 73.02 |
| Constant-rate grid | 5/6 | 58.26 |
| Differential evolution | 5/6 | 54.39 |
| `tokendance/glm-5.3` | 5/6 | 44.99 |
| Sobol search | 5/6 | 44.93 |

Both GPT and DeepSeek routes produced feasible designs on all six sealed cases in this run. Six cases with one attempt each do not establish a stable ordering between models. The GLM route recorded 14 HTTP 502 requests across the full 12-case matrix (5 on sealed cases), so its scores also reflect route reliability and the frozen retry policy. All 36 formal submissions were complete; no native solver failure occurred. Seven of the 72 agent/baseline designs failed a safety gate and retain their zero scores.

The [full leaderboard](results/pilot-v2/README.md), [machine-readable scores](results/pilot-v2/leaderboard.json), [failure/resource accounting](results/pilot-v2/FAILURES.md), and [independent audit](results/pilot-v2/audit.json) are included. The audit recomputed 1,296 native trajectories with maximum metric discrepancy 1.42 × 10⁻¹⁴. See [validation](docs/VALIDATION.md) and the separately retained [original development calibration](results/pilot-v1/CALIBRATION.md).

![Per-instance safe TIR, including every formal trial and the three baselines](results/pilot-v2/scorecard.png)

## Frozen boundary

The [original JSON contract](contract/contract.json) and two explicit amendments define the effective protocol. [Amendment 001](contract/amendment-001-models.json), requested before scored runs, replaces Opus with newer routed models and increases the pilot from 2 to 3 models. [Amendment 002](contract/amendment-002-interaction-budget.json) changes the interaction profile after development-only calibration, before any sealed model trial: 6 → 12 model calls, remaining-budget feedback, and an early-artifact reminder. CPU, wall time, total completion-token budget, cases, and scientific scores stay unchanged. Original failures remain archived separately.

- **Input:** known cohort, native TDI values, fixed material/finite-reservoir bounds, public physiology, and one provided training meal seed with ordinary/missed-lunch/large-dinner variants. Agents may generate additional training scenarios inside the same CPU budget; the simulator is public.
- **Output:** one shared static responsive parameter vector or constant rate, plus `search.py` and `rationale.md`. Dose amplitude and reservoir scale by each patient's TDI. No custom real-time controller or physiology edits.
- **Budget:** 1 CPU, 2 GiB memory, 30 cumulative container CPU seconds after JIT warmup; 90 tool wall seconds; 360 seconds including API waits; at most 12 model calls and a nominal 18,000 completion-token allowance. The runner reserves 0.3 CPU seconds for monitoring/pause latency and reports observed CPU. Token accounting uses successful-response usage (or a conservative 6,000-token fallback when absent). Failed requests still consume calls and wall time, but their token consumption is unavailable; the allowance is not a verified cap on all upstream inference or billing.
- **Independent evaluation:** native simglucose dopri5 resimulation over 3 days, 2 new seeds × 3 variants × 3 patients. First-day warmup is omitted from TIR/TBR but included in the minimum glucose check.
- **Safety gate:** EVERY patient/scenario must have TBR70 ≤ 4%, TBR54 ≤ 1%; EVERY minute including warmup must have glucose ≥ 40 mg/dL. Missing/invalid output and failed simulation score zero. Infrastructure errors remain visible separately.
- **Scores:** rank by feasible-case rate, then mean `safe_tir`. `safe_tir` is mean TIR [70,180] for a feasible design and zero otherwise. Raw TIR and worst-case safety are also reported. No explanation-based LLM judging.

## Run locally

Python 3.12, Docker with cgroup v2, and a shell are required. The first image build downloads scientific dependencies. No network is available inside trial containers. The pilot uses Linux/arm64 on an Apple M5 host; CPU-time-limited comparisons depend on hardware speed and should use a common environment.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install setuptools==80.10.2 wheel==0.48.0
.venv/bin/python -m pip install --no-build-isolation -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip install pytest==9.2.0
.venv/bin/python -m pytest -q
docker --context default build -t gri-bench:0.1.1 .

# One strong baseline on an open development instance.
.venv/bin/python -m gri_bench.runner --case dev-01 \
  --method differential_evolution --context default --tag my-run

# Independently resimulate the saved submission and export its result.
.venv/bin/python -m gri_bench.evaluate \
  private/runs/my-run/dev-01__differential_evolution__seed20261111 \
  --export results/my-run

# OpenAI-compatible routed agent; credentials remain only on the host.
export GRI_MODEL_BASE_URL=http://127.0.0.1:3425/v1
# If the endpoint requires it: export GRI_MODEL_API_KEY=...
.venv/bin/python -m gri_bench.runner --case dev-01 --method agent \
  --model YOUR_ROUTE --context default --tag my-agent
```

Commands in the original pilot use the local `colima-etbench` Docker context. Pass your own context for standalone trials. The suite script is the maintainer entry point for all 12 cases; it requires the private sealed inputs. Public users can reproduce the six development cases without them. The original private suite is never regenerated from public hashes.

## Baselines and model evidence

Three frozen algorithms receive the same CPU cap: constant-rate log grid, scrambled Sobol search, and logarithmic differential evolution. Their training target uses a predeclared safety margin (3% / 0.5% / 45 mg/dL). Their 36 verified runs are reused from `pilot-v1`: they do not call an LLM and are unaffected by the interaction-profile change. Candidate counts are diagnostic only: a white-box simulator permits custom evaluations and approximations.

The model matrix is recorded in [pilot-models.json](contract/pilot-models.json): `codex/gpt-6.1-sol`, `wanjie/deepseek-v4.1-flash-1017`, and `tokendance/glm-5.3`; one trial per instance/model. Magpie aliases and API-returned model strings are recorded. They do **not** independently authenticate the upstream checkpoint or provider configuration. Inference effort is the provider default, temperature is requested as zero, and actual returned token usage is retained. Billing cost is unknown, not zero.

The identifier `seed20261111` is the baseline RNG seed and trial label. No LLM sampling seed is sent to the routed API; agent-written searches choose their own seeds. Temperature zero does not establish deterministic replay across providers.

[DeepSeek's official changelog](https://api-docs.deepseek.com/updates/) identifies the 1017 update. The [DeepSeek weight card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) lists MIT; the [GLM 5.3 card](https://huggingface.co/zai-org/GLM-5.3) publishes weights under its own GLM-5.3 license. These sources establish public model availability, not the identity behind a third-party route.

## Separation and audit

The Docker image has an explicit source allowlist. It contains no instance files, sealed seeds, account configuration, API key, Docker socket, or host repository mount. Each task receives only its own training instance. Containers run as a non-root user with networking disabled, a read-only root filesystem, no added capabilities, bounded writable tmpfs, and process/memory/CPU limits. They are paused while the host waits for a model response.

The verifier runs trusted code outside the agent container. It parses bounded regular-file JSON and never imports submitted Python. Search code and rationale are archived as evidence; their presence and Python syntax are checked, but full search-code replay is not a scored requirement. Archived model code is untrusted: reproduce it inside the task sandbox. Native trajectories and per-scenario metrics are retained. Public exports include development designs/transcripts/traces, aggregate sealed-case results, and SHA-256 hashes of private evidence. Complete sealed inputs, their evaluation seeds, traces, and transcripts remain private.

Some development agents generated extra training seeds whose numeric values coincide with sealed-case **training** seeds. These original development records are retained. Private evaluation seeds are distinct and were not found in the public export; training-seed overlap is disclosed in the publication audit.

The [sealed manifest](contract/sealed-manifest.json) commits all six private cases using SHA-256 with a random 256-bit salt in each case. Local Git history records contract freeze before search; this is not an independently timestamped public preregistration. Prompt, baseline, runner, and image are frozen before the scored matrix; technical repairs must retain earlier attempts and disclose why they were necessary.

## Scientific provenance

Physiology and meal bookkeeping derive from [simglucose 0.2.11](https://github.com/jxx123/simglucose), with native 13-state dynamics unchanged. A Numba RK4 implementation accelerates search; the native environment/dopri5 implementation verifies submissions. Continuous release avoids pump quantization. Meals scale by BW/86.0704. This benchmark introduces a finite reservoir for the constant comparator as well as the responsive design, and uses stricter trajectory-level safety than the earlier prescreens.

The previous v1 STOP and v2 CONTINUE prescreen findings are historical results, not benchmark scores, and were not modified. V2 exposed substantial individual hypoglycemia despite favorable aggregate relative TIR; the new benchmark therefore uses explicit absolute, per-trajectory safety gates. The gates are benchmark criteria, not validated clinical treatment recommendations.

MIT license for benchmark code; see [third-party notices](THIRD_PARTY_NOTICES.md) for simglucose attribution. Version and dependency locks, image ID, source commit, model request/response identity, budget consumption, errors, and artifact hashes accompany the results.
