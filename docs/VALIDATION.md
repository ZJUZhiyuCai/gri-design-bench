# Validation record

## Original pilot

The contract was committed at `677446f` before benchmark searches. The two-route preflight selection was committed at `f4f4329`; the user then explicitly removed Opus and requested newer models plus open models. Amendment 001 records the revised three-route matrix. The runtime, fixed prompts, baselines, source/input hashes and final image were committed at `603095c` before scored searches. No scored Opus trial was run.

Preflight repairs addressed two container filesystem issues before the scored matrix: Numba requires a writable cache directory, and the Docker archive API in this runtime cannot retrieve tmpfs output. The final image seeds a writable cache during excluded warmup. A fixed isolated artifact reader stops other user processes and collects only bounded regular files; it never imports submitted code. Failed preflight attempts were environment checks, not model score attempts.

Evidence collected before model trials:

- Fast 3-day RK4 versus native dopri5 check: maximum plasma difference approximately 0.0000201 mg/dL; identical TIR for the checked responsive design.
- Native compiled RHS is compared against the original simglucose implementation through meal-containing trajectories. Finite-reservoir depletion is checked for both release modes.
- Safety tests confirm that one failing trajectory or a low-glucose warmup minute invalidates a design; cohort averaging cannot conceal it.
- Strict JSON rejects duplicate keys, NaN, infinity, unknown parameters and out-of-range doses. Changed submission hashes are rejected. Submitted Python is never run by the verifier; prose claims are ignored.
- Live Docker controls confirm non-root execution, no networking, no host configuration or Docker socket, source write protection, symlink rejection, and interruption of continuous compute at about 29.92 measured CPU seconds. The raw control record is in `results/controls/sandbox.json`.
- The parent research repository's 490 protected v1 file hashes remain identical; all 185 existing tests pass. No original tracked file was modified.

The 36 baseline runs were independently audited across 648 native trajectories, with maximum recomputation error 1.42e-14. Their results were committed at `9a9b697` before model trials. The first model profile then completed 11 development trials and interrupted 2; it never reached any sealed model instance. Eight completed trials failed artifact submission, while three produced complete submissions. This development evidence prompted Amendment 002, recorded before the revised profile: 12 model calls instead of 6, explicit remaining budgets, and an early-artifact reminder. All 21 scientific/data/dependency files covered by the unchanged-file check retain their previous hashes. No original case, scientific score, threshold or baseline result was changed. Prior baseline sealed scores were known, which is explicitly disclosed in the amendment.

The original calibration records are retained in `results/pilot-v1/CALIBRATION.md`; they are not pooled into the revised model leaderboard. The three algorithms' original runs are reused because they have no model interaction and the scientific environment and local CPU limit are identical. The mock-model integration control exercises all 12 calls and checks the budget feedback without contacting an external model.

The revised prompt, runner, source/input hashes and image were frozen at `31b6b0c` before any sealed model trial. All 36 formal model metadata records identify that commit. The final [audit](../results/pilot-v2/audit.json) covers 36 new model runs plus 36 reused baseline runs: all 72 designs completed native verification, and 1,296 saved native trajectories were independently recomputed. Maximum metric discrepancy is 1.42e-14; maximum recorded container CPU is 29.94829 seconds. Seven designs failed scientific safety gates and retain their zero scores. There were no missing/invalid formal submissions or native solver failures. All public sealed result directories contain aggregate JSON only.

The 36 model trials recorded 14 HTTP 502 requests, all on the GLM route. The existing retry/stop policy was applied without a rerun or a budget extension. Failed requests consume call and wall budgets, but return no usage record: the nominal completion-token allowance is not a verified total-inference or billing cap. [Failure/resource accounting](../results/pilot-v2/FAILURES.md) reports usage and errors separately from scientific scores.

A clean public-only Git checkout, with a separate Python environment and no sealed input files, passed all **12 tests in 52.06 seconds**. The public GitHub workflow runs the same source, scoring and submission-boundary tests without model credentials. The verifier environment is recorded in `results/controls/native-verifier-environment.json`.

The [publication audit](../results/controls/publication-audit.json) checks the public worktree and Git history against locally configured credentials and private evaluation seeds/salts, verifies all 32 runtime-lock files and all six sealed commitments, and rechecks the original 490 protected research files. Some development agents independently generated additional training seeds whose numeric values coincide with sealed-case training seeds; their original records are retained. These are not private evaluation seeds. Complete sealed inputs and raw sealed transcripts remain private, so full independent reproduction of sealed results requires those inputs; development results are reproducible from this repository.

The freeze evidence is local Git history and cryptographic file commitments, not independently timestamped public preregistration. The first public release occurs after this pilot, including its protocol amendments and calibration history.

The original pilot is deliberately small: one task family, six cases in each split, one run per route/case, public patient physiology, and unknown upstream routing/inference defaults. Those scores support a harness pilot and expose design failures; they do not establish a statistically stable model ranking, a global optimum, or clinical performance.

## Three supplemental repetitions, 2026-11-11

The [GLM route investigation](GLM_502_DIAGNOSIS.md) recovered the original failed-request usage: all 14 errors reached their output caps, consuming 62,029 completion tokens omitted by the old runner. Ten of the twelve original GLM trials exceeded the nominal allowance. Original result files and `v0.1.1` remain intact, with this limitation explicitly recorded.

The repaired host entry point reserves every request's output cap, including failed requests. A real Docker / mock API control and eleven targeted tests verified the repair before execution. The supplemental plan and its 11-file implementation lock were published at **`e225372ed7e5f318888dc3f2024dffbf519d2689`**, tagged **`repeats-2026-11-11-plan`**, and passed GitHub CI before the scored suite began. All 108 new trial records identify that source commit and the original image ID. No scientific input, prompt, model setting, numeric budget, original runtime file, or stop policy changed during the suite.

Both the 108-trial runner and native grader exited successfully. The [supplemental audit](../results/repetitions-2026-11-11/audit.json) verifies:

- Exact coverage of 3 routes × 12 cases × 3 repetitions; no omitted or replacement attempts.
- All 108 saved initial prompts against the frozen system prompt, task and case inputs; all 2,769 private evidence hashes against the public commitments.
- Every one of 964 API request reservations; maximum charged completion allowance 18,000, no reported successful usage above a requested cap, and no unclassified infrastructure fallback reservation.
- 99 valid designs and 1,782 saved native trajectories, with maximum independent metric discrepancy **1.42e-14**. Nine submission failures and eleven additional safety failures retain zero scores. There were no native solver or infrastructure failures.
- All **367 original result files** and **32 original runtime files** unchanged; the supplemental 11-file lock also verifies.

One development GPT trial (`repeat-20261111-r2`, `dev-01`) recorded **30.311041 CPU seconds** under the unchanged polling monitor. No other recorded resource limit was exceeded: maximum total wall time was 332.578467 seconds and maximum cumulative tool wall time was 34.711643 seconds. The primary results retain the original native scores. A clearly labelled secondary sensitivity, introduced after observing the development overrun, assigns infeasible/zero to every over-limit attempt without dropping it. It leaves all three round orderings unchanged on both splits. No sealed trial has a recorded resource exception.

The first sealed validation failure exposed a publication issue: the frozen validator's out-of-bounds error contains private numeric bounds. The publication-only helper removes this diagnostic detail, while preserving the private score and original export bytes. Exactly one public `score.reason` was changed; every numeric field is identical. The [redaction manifest](../results/repetitions-2026-11-11/publication-redactions.json) records before/after hashes. The native audit verifies exact redaction coverage and recomputes metrics using the original audit's arithmetic. Frozen execution and verifier code were not edited. Six new tests cover privacy, unchanged scores, preserved originals, idempotent publication, recovery after an interrupted manifest write, and rejection of tampered scores.

The final local suite passed **29 tests in 9.36 seconds**, with five existing dependency deprecation warnings. The analysis was also checked on synthetic complete matrices for ties, fixed denominators, failed submissions, variance, and resource-sensitive rankings, then cross-checked against the real per-trial score sums. The exported figure was visually inspected.

The completed [stability report](../results/repetitions-2026-11-11/README.md) preserves the original pilot separately. All three new sealed rounds order GPT > DeepSeek > GLM; the mean safe TIR across round means is 75.06 ± 0.63, 62.97 ± 7.40, and 23.40 ± 18.22, respectively. These SDs describe three observed rounds, not confidence intervals. Existing sealed scores were already known to the maintainer; this is repetition on fixed cases, not new holdout validation or a population-level ranking.

For a maintainer with the original private evidence, reproduce the publication and audit with:

```bash
python -I scripts/sanitize_repetition_exports.py
python -I scripts/audit_repetitions.py
python -I scripts/analyze_repetitions.py
python -I scripts/plot_repetitions.py
```

The last two commands regenerate the descriptive report and figure from the public results. The full sealed trajectory audit requires the private evidence. The new [publication audit](../results/repetitions-2026-11-11/publication-audit.json) checks credentials, private evaluation seeds/salts, original research preservation and public Git contents; the original publication-audit file is retained byte-for-byte.

## Six additional routes, preregistered 2026-11-11

The [six-route expansion protocol](MODEL_EXPANSION_2026_11_11.md), model registry, connectivity evidence, 216-job schedule, preservation manifest and 15-file execution lock were published at **`354c2b33e219d08ad71b3904855bd820f9ed7a7f`**, tagged **`expansion-2026-11-11-plan`**, before scored trials. The plan-tag CI passed before execution; branch CI also passed. All six selected explicit routes passed the same non-benchmark mock tool roundtrip. The two failed Nemotron connectivity attempts were retained, and Intern-S2 replaced it before scoring. No Claude-family route was selected.

Both the 216-trial runner and grader exited with status zero. Every new trial records the plan commit, the original image and `strict-token-accounting-v1`. The scientific contract, prompts, cases, seeds, evaluator, model settings, configured budgets and two-error stopping rule were unchanged. The new wrapper schedules and safely exports results through the frozen runner and scorer; postprocessing code does not participate in agent execution.

The [expansion audit](../results/expansion-2026-11-11/audit.json) verifies:

- Exact coverage of six routes × twelve cases × three contexts: 36 attempts per route and 72 per repetition tag, with no omitted, replacement or best-of-three attempts.
- All 799 previous result files, 32 original runtime files, 11 earlier repetition files and 15 new execution-lock files unchanged.
- 215 saved initial prompts, 1,480 saved response model/usage records, 4,538 private evidence hashes and all 216 publication receipts. One MiMo development attempt ended after two API errors before any successful reply, so no transcript was saved; its failed attempt and ledger remain included.
- All 1,608 request reservations, with at most 18,000 charged completion tokens per attempt, no reported successful usage beyond a requested cap and no unexpected infrastructure reservation. The 128 API-error requests are retained separately from trial outcomes.
- 112 valid designs and 2,016 saved native trajectories, with maximum independent metric discrepancy **1.42e-14**. There are 104 submission failures, 36 additional safety failures and 76 feasible attempts. No native solver or infrastructure failure occurred.

Thirteen new attempts have recorded resource-limit excesses: one development CPU value of **30.225626 seconds**, and twelve total-wall values above 360 seconds, with a maximum of **360.490869 seconds**. Maximum cumulative tool wall time is **33.351685 seconds**. Eleven exceptions are development attempts and two are sealed attempts. The polling monitor and limits were not changed. The preregistered secondary analysis assigns zero/infeasible to every over-limit attempt without dropping it or changing a saved primary score. It changes the development aggregate ordering and the new cohort’s first-round ordering on both splits; the combined sealed aggregate ordering remains unchanged. Intern-S2’s only feasible sealed attempt becomes zero under this rule. The earlier cohort’s one development CPU exception remains separately labeled as previously disclosed.

The publication filter redacted exactly one new sealed diagnostic. Original export bytes and private scores remain intact; only `score.reason` differs publicly, and every numeric value is unchanged. The [new redaction manifest](../results/expansion-2026-11-11/publication-redactions.json) verifies all 216 receipts and preserves before/after hashes. Sealed public trial directories contain only aggregate result JSON. Development evidence is copied byte-for-byte from the staged export, including the filtered transcript format used by the frozen exporter.

The final local suite passed **39 tests in 11.04 seconds**, with five existing dependency warnings. New synthetic complete-matrix tests cover ties, fixed denominators, omitted/duplicate attempts, unchanged inputs and the effect of resource zeroing on per-round and aggregate ranks. A separate synthetic report/CSV/figure roundtrip passed; fixture data were not published. Actual native arrays were independently recomputed, and the final comparison figure was visually inspected.

The [nine-route report](../results/expansion-2026-11-11/README.md) combines the new 216 attempts with the earlier 108 strict-accounting attempts, retaining the chronological batch labels. It cross-checks every reused earlier model summary against the protected earlier report. Kimi and Qwen rank first and second among the new six in every sealed round, but their round means vary substantially; the remaining ordering changes. The fixed sealed cases have already been used, so this is repeatability on known benchmark instances, not new holdout validation. Original pilot model scores and single-run baseline references remain separate.

After collecting the complete matrix, reproduce the expansion analysis with:

```bash
python -I scripts/audit_expansion.py
python -I scripts/analyze_expansion.py
python -I scripts/plot_expansion.py
```

The audit requires original private evidence. Analysis and plotting use the complete public results and preserve every earlier result file. The new [publication audit](../results/expansion-2026-11-11/publication-audit.json) checks public files and Git history against local credentials and private evaluation seeds/salts, verifies sealed commitments and rechecks all 490 protected original research files.
