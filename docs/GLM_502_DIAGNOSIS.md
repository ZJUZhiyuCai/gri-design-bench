# GLM 502 diagnosis and completion-budget repair

Date: 2026-11-11 (Asia/Shanghai). The original `v0.1.1` release and primary trial results are retained unchanged.

## What the records establish

All **14 formal GLM HTTP 502 errors** match Magpie routing records inside the corresponding trial time windows. Every failed generation reached its actual requested output cap, between **1,743 and 6,000 tokens**. Magpie classified every one as an empty reply truncated at the length limit after spending the output on reasoning. Together, the failed requests reported **62,029 completion tokens**, including **61,992 reasoning tokens**.

The benchmark runner received an HTTP error and omitted that usage from its completion counter. Adding the router-reported failed usage to successful-response usage shows that **10 of the 12 original GLM trials exceeded the nominal 18,000-token allowance**. The earlier README already said failed-request usage was unavailable to that runner; this investigation supplies the missing evidence. The original scores are historical records, not evidence of strict completion-budget compliance.

The [machine-readable diagnosis](../results/controls/glm-502-diagnosis.json) contains per-trial recovered totals and evidence hashes. Raw account routing logs, credentials, sealed prompts and private model responses are not published. The counters are local router telemetry, not independently audited billing or upstream-model authentication.

## Bounded replay

One original **development** request was reconstructed and sent once through Magpie and once directly to the same configured upstream service, using its original 2,012-token cap, temperature zero, messages and tools. Both returned HTTP 200. The Magpie replay ended with `finish_reason=length` and malformed tool-argument JSON; the direct replay returned a valid tool call. No tool from either replay was executed, and neither replay is a scored trial. This demonstrates present connectivity while retaining evidence of output truncation; it does not prove the failure disappeared or isolate a causal difference between the endpoints.

Z.ai's [parameter documentation](https://docs.z.ai/guides/overview/concept-param) describes GLM-5.3 as a thinking model and lists `max` as the default reasoning effort. Its [API reference](https://docs.z.ai/api-reference/llm/chat-completion) exposes length termination and completion usage. These documents provide context; the benchmark retains the routed provider's defaults and cannot authenticate their exact upstream implementation.

## Repair within the existing task contract

The normative [contract](../contract/contract.json) specifies 6,000 completion tokens per call and 18,000 per trial. Its [repair rule](../contract/README.md) permits implementation repairs that preserve the contract and earlier attempts. No case, seed, design bound, safety criterion, prompt, reasoning parameter, model route, CPU/memory/wall limit, API-call limit or existing retry/stop rule is changed. Magpie's configuration is not modified.

The new host-only `strict-token-accounting-v1` entry point reserves the entire requested cap before each API attempt. A valid successful usage report releases its unused portion. A failed request or missing/invalid usage report releases nothing. A retry therefore cannot obtain free completion tokens. Provider usage exceeding the requested cap is recorded as a violation and stops the trial. The original runner and all 32 files in its runtime lock remain byte-identical; they are retained for historical reproduction.

Eleven targeted tests cover conservative accounting, reduced final request caps, invalid usage, unchanged successful-response requests/prompts, and the existing two-error stop. A real Docker / mock API control requests `[6000, 6000, 6000, 3000]` tokens, including two synthetic errors, and stops at 18,000 accounted tokens while retaining the initial submission. It makes no external model call. See [control evidence](../results/controls/token-accounting-repair.json).

The [supplemental plan](../experiments/repeats-2026-11-11/plan.json) registers three new attempts per model/case, **108 trials total**, all using this repaired accounting. Their stability analysis is separate from the original pilot. In particular, the original GLM run is not pooled with the repaired runs as a homogeneous fourth repetition. Output truncation may still occur at the unchanged limit; increasing that limit or changing reasoning settings would be a different experiment.
