# GRI reservoir-attribution pilot

Eight scored agent runs on 17 November 2026 used one frozen Harbor task. The task asks the agent to distinguish the effect of release timing at matched daily doses from the effect of early reservoir depletion under matched initial loading. It retains dev-03 as the response-delay control. Each measurement policy has one unit of budget.

Agents analyze simulated release and glucose trajectories, submit a planning report and provide a runnable script. A separate offline verifier compares the submitted report, a clean visible replay and a hidden replay with the reference. The held-out panel uses 32 fresh meal seeds per candidate, three variants per seed and the same three virtual patient profiles per candidate. Passing all 13 checks earns 1.

| Model or reference | Passed / runs | Median end-to-end time (s) | Total estimated API cost (USD) |
|---|---:|---:|---:|
| Fixed reference | 1 / 1 | 39.7 | 0.0000 |
| GPT-6 Astra | 5 / 5 | 153.2 | 2.3816 |
| GPT-6.1 Sol | 1 / 1 | 149.7 | 0.0935 |
| DeepSeek V4.1 Flash | 0 / 1 | 286.1 | Unavailable |
| Kimi K3.1 Pro | 1 / 1 | 201.1 | Unavailable |

End-to-end time includes environment setup and verification. Astra and Sol used the official OpenAI Responses API with high reasoning and Standard rates. Cost estimates use returned token counts and cache rates. DeepSeek and Kimi used the Magpie gateway with its default reasoning settings and token counts. Gateway billing amounts were unavailable. These are repeated observations on one task, with different run counts and route settings. [Per-run data](summary.json) · [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

## Failure and recovery

- **DeepSeek V4.1 Flash** used the visible panel to exercise its holdout code path and overwrote the planning report. The cumulative request limit stopped the run before it regenerated that report. With no locked planning decisions in the submitted output, the verifier returned 0 before running either replay. A separate fresh-container check of the submitted script passed all 13 checks with no additional model calls. The score table counts the original trial.
- **Kimi K3.1 Pro** recovered from three NumPy array-shape errors during self-check and passed both replays. Its cumulative request allowance was 3 MB, compared with 1.5 MB for the other runs. It used about 0.33 MB.

The model runs, raw trajectories, hidden answers and submitted scripts are archived locally. This report includes the task checksum, trial scores, timing and token counts.
