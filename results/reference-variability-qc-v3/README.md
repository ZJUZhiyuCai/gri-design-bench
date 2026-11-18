# Reference variability and quality control

[简体中文](README.zh-CN.md)

This pharmacy task tests whether a model can use repeat peak-exposure measurements, sample traceability and batch quality records to decide whether wider bioequivalence limits are justified and what a paper may conclude about its peak-exposure endpoint. Under the study rules, widening is considered only above 30% within-subject reference variability, with adequate repeat-measurement evidence for flagged samples. Each submission is a program that must handle new dossiers.

The extension adds Sol, Terra and Luna to previously sealed Astra and fixed-control results on the same task. Forty synthetic crossover panels each have nine paired evidence variants. Nine additional dossiers check invariance to renaming and row order. Each model made five attempts in fresh contexts. Every delivered script faced the same 369 inputs twice. Whole-task reward is 1 only when the numerical fields, record identifiers, permission and claim all pass and the two runs agree.

| Model | Whole-task passes | 95% Wilson interval | Delivered | API interruptions | Deliveries with an interpretable scientific error in the primary dossiers | Median agent seconds | Estimated API USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Astra | 5/5 | 56.6%–100.0% | 5/5 | 0 | 0 | 64.3 | 1.4645 |
| GPT-6.1 Sol | 5/5 | 56.6%–100.0% | 5/5 | 0 | 0 | 54.9 | 0.2898 |
| GPT-6.1 Terra | 5/5 | 56.6%–100.0% | 5/5 | 0 | 0 | 103.6 | 0.1850 |
| GPT-6 Luna | 5/5 | 56.6%–100.0% | 5/5 | 0 | 0 | 65.1 | 0.0242 |

All models used the official Responses API with high reasoning and the same terminal tool. Each attempt allowed 40 requests, 96,000 output tokens and 1.5 MB of cumulative request bytes. Hidden scoring followed collection. Each dossier ran in a fresh offline container with one CPU, 2 GiB of memory and 45 seconds. An API interruption can still leave a gradeable script. Missing submissions receive zero end to end. Costs are estimates from returned usage receipts. [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

## Controls and scientific decisions

| Fixed policy | Fully correct dossiers on first / second pass (369 each) | Claims /360 | Exact missing evidence /84 | Correct holds /28 | Reward |
|---|---:|---:|---:|---:|---:|
| Evidence-aware reference | 369 / 369 | 360 | 84 | 28 | 1 |
| Always trust variability | 278 / 278 | 332 | 0 | 0 | 0 |

In 84 primary dossiers, the evidence for widening the limits is pending. For 28 of these, the choice of limit changes the endpoint decision and the claim must be held. Of the remaining dossiers, 21 support equivalence under both limits and 35 lack support under both. Both controls use the same statistical calculation. The shortcut incorrectly reports support for all 28 decision-sensitive dossiers.

The table below counts submitted programs. A program contributes to a column only if it passes every relevant case in that column.

| Model | Exact records in all 84 dossiers with gaps | All 28 required holds | All 56 determinate claims with permission marked pending | All four double-gap panels across repairs | Stable replay |
|---|---:|---:|---:|---:|---:|
| GPT-6 Astra | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| GPT-6.1 Sol | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| GPT-6.1 Terra | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| GPT-6 Luna | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

## Difficulty and verification

All four models passed every attempt, above the original calibration target of 40% (two passes in five). Each difficulty estimate comes from five attempts on one synthetic task. The many paired dossiers exercise the submitted programs. The task supplies a numerical estimator and explicit audit rules, so the scores measure implementation of evidence-aware analysis under those rules. Source inspection found a direct call to the supplied estimator `pk_model.summarize` in 20 of 20 delivered scripts.

The fixed controls show that ignoring quality records changes what a paper may claim. This makes the task a useful baseline check of evidence handling.

The 15 additional attempts took 23.3 minutes from first start to collection lock. Estimated API cost was USD 0.4990. Their 11,070 isolated dossier executions took 69.8 minutes summed on verifier monotonic clocks and 114.7 minutes of wall time from the first to last pass. The host entered sleep and wake cycles during verification. The original verifier enforces its wall budget on a monotonic clock.

[Original task prompt](instruction.md) · [Public practice input](example.json) · [Per-attempt scores, times and costs](summary.json) · [Freeze manifest](freeze.json)
