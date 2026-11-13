# GRI Design Bench v0.2 nine-route comparison

Six more routes ran 216 attempts on the original v0.2 cases. The comparison combines those runs with the first three routes, for 324 model attempts and 24 fixed baseline runs. Each attempt has 30 CPU seconds for search. Eligible designs for a given case use the same independent panel of 144 trajectories.

## Sealed cases

| Rank | Model | Valid designs | Safety passes | Mean score (%) | Round ranks | Round mean SD | Rank omitting one case | vs. constant (pp) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GPT-6.1 Sol | 18/18 | 18/18 | 73.11 | 1 / 1 / 1 | 0.48 | 1–1 | +23.63 |
| 2 | DeepSeek V4.1 Flash 1017 | 18/18 | 14/18 | 51.97 | 3 / 3 / 4 | 3.12 | 2–4 | +2.49 |
| 3 | MiniMax-M3.1-Flash | 16/18 | 14/18 | 51.82 | 5 / 2 / 2 | 17.07 | 2–4 | +2.34 |
| 4 | MiMo-V2.6-Pro | 15/18 | 11/18 | 46.47 | 2 / 5 / 3 | 11.22 | 3–5 | -3.01 |
| 5 | Kimi-K3.1-Pro | 18/18 | 14/18 | 44.23 | 4 / 4 / 5 | 7.24 | 3–5 | -5.25 |
| 6 | Step-5-Preview | 16/18 | 10/18 | 33.39 | 6 / 6 / 6 | 10.83 | 6–6 | -16.09 |
| 7 | GLM-5.3 | 18/18 | 9/18 | 20.95 | 7 / 7 / 8 | 0.53 | 7–8 | -28.53 |
| 8 | Qwen3.8-27B | 8/18 | 5/18 | 17.06 | 9 / 8 / 7 | 15.79 | 7–8 | -32.42 |
| 9 | Intern-S2 | 3/18 | 2/18 | 8.20 | 8 / 9 / 9 | 7.12 | 9–9 | -41.28 |

The fixed baselines scored 49.48% for constant release and 58.03% for responsive release.

GPT-6.1 Sol and DeepSeek V4.1 Flash 1017 are the top two by mean score. Their matched case-mean gap is 21.14 points with a 95% case bootstrap interval of [+10.13, +31.10]. Bootstrap resamples keep the three repeats of each case together.

## Ranking stability

GPT-6.1 Sol led all three combined rounds and remained first when any single case was omitted. Of 36 model pairs, 29 kept their order and 7 reversed it across rounds. DeepSeek and MiniMax were 0.15 points apart overall, with a paired 95% case bootstrap interval of [−15.55, +16.03].

| Ranking | Sealed round-pair τ-b range | Development round-pair τ-b range |
|---|---:|---:|
| Nine routes, aligned by repeat index | 0.67–0.83 | 0.08–0.60 |
| Six new routes, same batch | 0.73 | 0.00–0.86 |
| First three routes, same batch | 0.33–1.00 | -0.33–0.33 |

Kendall's τ-b measures whether pairs keep their relative order. It reaches 1 when rankings agree. The combined table aligns repeat numbers from two chronological batches. The two within-batch rows compare runs made together. Omitting each case in turn shows how much a single case influences the aggregate rank.

The three-route pilot ran 11-13 00:42 to 11-13 02:38 (Beijing time). The six-route expansion ran 11-13 09:16 to 11-13 13:02 (Beijing time). Differences across these batches can include changes in the routed services.

## Development cases

| Rank | Model | Valid designs | Safety passes | Mean score (%) | Round ranks | Round mean SD | Rank omitting one case | vs. constant (pp) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | DeepSeek V4.1 Flash 1017 | 18/18 | 14/18 | 47.57 | 2 / 1 / 3 | 4.70 | 1–2 | +0.60 |
| 2 | GPT-6.1 Sol | 18/18 | 12/18 | 45.90 | 5 / 2 / 1 | 19.79 | 1–2 | -1.07 |
| 3 | Kimi-K3.1-Pro | 18/18 | 14/18 | 41.14 | 1 / 4 / 4 | 10.37 | 3–3 | -5.83 |
| 4 | MiMo-V2.6-Pro | 14/18 | 10/18 | 37.34 | 8 / 5 / 2 | 25.21 | 4–4 | -9.64 |
| 5 | Step-5-Preview | 17/18 | 11/18 | 24.55 | 3 / 7 / 6 | 14.06 | 5–6 | -22.42 |
| 6 | MiniMax-M3.1-Flash | 15/18 | 7/18 | 22.46 | 6 / 3 / 7 | 12.81 | 5–7 | -24.51 |
| 7 | GLM-5.3 | 18/18 | 9/18 | 21.69 | 9 / 6 / 5 | 16.62 | 5–7 | -25.29 |
| 8 | Qwen3.8-27B | 7/18 | 3/18 | 10.63 | 4 / 8.5 / 8.5 | 18.41 | 8–9 | -36.34 |
| 9 | Intern-S2 | 4/18 | 4/18 | 8.52 | 7 / 8.5 / 8.5 | 14.75 | 8–9 | -38.46 |

The development round leaders were Kimi-K3.1-Pro / DeepSeek V4.1 Flash 1017 / GPT-6.1 Sol. DeepSeek's aggregate lead over GPT was 1.68 points.

## Trial evidence

Of the 216 new attempts, 102 passed the safety checks, 53 failed them, 60 lacked a valid submission, and one exceeded the CPU budget.

| New route | Valid designs /36 | Submission failures | Safety failures | Response timeouts | Other API errors |
|---|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash 1017 | 36 | 0 | 7 | 0 | 0 |
| MiMo-V2.6-Pro | 29 | 7 | 8 | 14 | 6 |
| Step-5-Preview | 33 | 3 | 12 | 0 | 6 |
| GLM-5.3 | 36 | 0 | 18 | 0 | 0 |
| Qwen3.8-27B | 15 | 21 | 7 | 36 | 0 |
| Intern-S2 | 7 | 29 | 1 | 36 | 2 |

API counts are per request. An attempt can receive a score after a later API error if it already submitted a valid design.

GLM made 372 API requests across both splits with no recorded errors. DeepSeek's third attempt on sealed case 04 submitted a legal design and used 30.59 CPU seconds. Its score is zero under the registered resource rule.

The audit checked 2,092 API reservations and aggregated 22,320 native trajectories. It independently reran 12 designs covering 1,728 trajectories.

Model names identify the requested Magpie routes. The registry records available public checkpoint references. The upstream serving versions and inference settings remain unverified.

[Leaderboard CSV](leaderboard.csv) · [Round ranks](rounds.csv) · [Paired differences](paired.csv) · [Case means](cases.csv) · [Leave-one-case-out ranks](leave-one-case-out.csv) · [Summary JSON](summary.json)

Regenerate the tables with `python scripts/analyze_v02_expansion.py --output /tmp/gri-v02-report`.

[New development attempts](development-attempts.json) · [New sealed attempts](sealed-attempts.json) · [Audit](audit.json) · [Registered expansion plan](../../../experiments/v0.2-expansion-2026-11-13/plan.json)
