# Six additional open-weight routes

This expansion adds **216 planned attempts**: six new routes × twelve unchanged instances × three fresh contexts. Together with the 108 strict-accounting attempts already published, the descriptive comparison will cover nine routes. The original pilot remains separate. No Claude-family or Opus route is selected.

The [registered plan](../experiments/expansion-2026-11-11/plan.json), [model registry](../experiments/expansion-2026-11-11/models.json), [connectivity evidence](../experiments/expansion-2026-11-11/connectivity.json), and [prior result hashes](../experiments/expansion-2026-11-11/prior-result-hashes.json) are committed before any new scored run. The pre-run source is tagged `expansion-2026-11-11-plan`.

## Selection

| Requested Magpie route | Public reference weights | Reference license |
|---|---|---|
| `atria/qwen3.8-27b` | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | Apache-2.0 |
| `minimax-code/MiniMax-M3.1-Flash` | [MiniMax-M3.1-Flash](https://huggingface.co/MiniMaxAI/MiniMax-M3.1-Flash) | MiniMax Community License |
| `workbuddy/kimi-k3.1-pro` | [Kimi-K3.1-Pro](https://huggingface.co/moonshotai/Kimi-K3.1-Pro) | Kimi K3.1 Pro License |
| `tokendance/mimo-v2.6-pro` | [MiMo-V2.6-Pro-RL](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL) | MIT |
| `workbuddy/step-5-preview` | [Step-5-Preview](https://huggingface.co/stepfun-ai/Step-5-Preview) | StepFun Model License 1.0 |
| `atria/intern-s2` | [Intern-S2-397B](https://huggingface.co/internlm/Intern-S2-397B) | Apache-2.0 |

The registry records the official repository revision, weight-file presence, and metadata observation time. “Open-weight” means the referenced weights are publicly available; several use custom model licenses. It does not certify the checkpoint, quantization, or inference implementation actually served by Magpie. Requested and returned labels are retained for every call, with provider-default inference settings.

Selection uses recent versions, different model families, public weights, and a non-benchmark mock tool roundtrip. No case inputs, optimization results, or scores enter selection. All six selected routes passed the same two-call diagnostic using the frozen shell-tool schema, temperature zero, 6,000 completion tokens per call, and a 120-second request timeout. No returned command was executed.

The initial `remote-magpie/zinal-supervl/nemotron-3.5-super-vl` candidate timed out twice, including a confirmatory connectivity check. Both failures are retained. Intern-S2 passed the same diagnostic and replaces it before scored trials. In total the probes attempted 14 requests. A timeout may have no HTTP response; the public diagnostic explicitly distinguishes attempted requests from completed HTTP responses.

## Unchanged experiment

- The exact system/task prompts, shell schema, physiology, instance inputs, bounds, training/evaluation seeds, safety gates, and scoring remain frozen.
- The unchanged `strict-token-accounting-v1` runner permits 12 calls, at most 6,000 completion tokens per request and 18,000 per trial, including failed-request reservations. It retains the same two-API-error stopping rule.
- The unchanged image and sandbox provide one CPU, 2 GiB, 30 search CPU seconds, 90 tool wall seconds, and 360 total agent wall seconds. API requests retain the existing timeout rule.
- Two trial workers and two trusted host grading workers are used. The case-major schedule rotates model order by case and repetition. Every planned attempt remains in the denominator; there is no best-of-three selection or silent rerun.
- All 799 previously tracked result files are protected by hashes. The original 32 runtime files and 11 supplemental implementation files remain unchanged.

The new host module only schedules the new matrix and publishes exports safely. It calls the unchanged trial runner and native evaluator. Raw exports remain in private staging; the existing sealed-error diagnostic filter is applied before an atomic public copy. Raw scores, original diagnostic bytes, and hashes are retained. Numeric scores are never edited by publication.

## Registered analysis

The primary split is the six fixed sealed instances. Rank by feasible-case rate, then mean safety-gated TIR, retaining ties. Each new model has 18 sealed attempts. Report all three round means, sample SD across those three means, feasible counts, per-case variability, per-round ranks among the six new routes, failures, API errors, and charged tokens.

The nine-route aggregate reuses the earlier three routes' 108 strict-profile attempts. It is a comparison across chronological batches, not a newly interleaved nine-route experiment. Do not compute cross-batch paired significance tests or treat the old pilot as another homogeneous repetition. Fixed baselines remain one-run references. The six sealed cases have already been scored by the maintainer; this does not test new unseen-case generalization.

A secondary strict-resource analysis is preregistered for this new cohort: any recorded resource-limit excess yields infeasible/zero in that view, with no tolerance and no dropped attempts. Primary native scores are preserved. The earlier cohort's corresponding analysis was added after its observed CPU overrun and remains labeled accordingly.

## Execution

Use the locked Python environment and existing Docker context/image. The model base URL is the same local Magpie endpoint used by the original runner. No account configuration or credentials belong in public git.

```bash
python -I scripts/run_expansion.py check
python -I scripts/run_expansion.py run
# In a second process, while the runner is active:
python -I scripts/run_expansion.py grade
```

Both execution commands require `HEAD` to equal the pre-run plan tag. Existing completed attempts are retained; unfinished directories stop resumption for explicit accounting. Public CI validates the file locks without requiring the final report commit to equal the execution commit.
