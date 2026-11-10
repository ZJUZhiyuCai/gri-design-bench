# Validation record

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

The final `results/pilot-v2/audit.json` is generated only after the revised model matrix finishes. It recomputes each metric directly from saved native arrays, checks artifact hashes, counts the 36 new model runs plus 36 reused baseline runs, and verifies that public sealed directories contain aggregate result JSON only. The public release retains failures. The sealed cases and raw sealed transcripts remain private, so full independent reproduction of the sealed results requires those inputs; development results are reproducible from this repository.

The benchmark is deliberately small: one task family, six cases in each split, one run per route/case, public patient physiology, and unknown upstream routing/inference defaults. The scores support a harness pilot and expose design failures; they do not establish a statistically stable model ranking, a global optimum, or clinical performance.
