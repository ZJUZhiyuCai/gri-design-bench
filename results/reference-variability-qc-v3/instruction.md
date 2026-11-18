# 从复测记录判断峰浓度等效证据

你负责复核一项教学用的四周期重复交叉试验。研究开始前的方案允许在条件满足时按参比个体内变异放宽 Cmax 界限。请交付 `/app/analyze.py`，运行方式为 `python analyze.py packet.json`。每次离线执行只会收到一份独立档案。向标准输出写一个 JSON 对象。`/app/example.json` 可供练习，镜像内可导入 NumPy、SciPy 和 `pk_model`。

## 阅读档案

`peaks` 是已经通过原分析质控的峰浓度观测，按 `subject`、`period`、`sequence` 和 `treatment` 区分，`sample` 标识产生该峰值的原始采样，`peak` 是其浓度。每位受试者各有两个 R 和两个 T 周期。下面三张表只属于一项补充调查。它们显示独立分装样的溯源关系 `links(sample, aliquot)`、指定复测读数 `repeats(aliquot, run, value)` 和该复测批次的原始质控 `qc(run, level, replicate, nominal, observed)`。分装与读数由标识关联，文件顺序无意义。批次校准、主分析样品有效性及其余质控均已确认。全部主测量都进入估计。

## 复核规则

1. 对数固定效应模型控制受试者（嵌套于序列）与周期，估计 T/R 几何均值比和双侧 90% t 区间。用仅含 R 的模型控制受试者及周期，得到 `sWR` 和 `reference_cv = sqrt(exp(sWR²) - 1)`。可直接使用 `pk_model.summarize(packet['peaks'])` 的数值结果。所有比较均使用未舍入值。
2. 对每位受试者计算 `d = (log(R晚) - log(R早)) / sqrt(2)`，按序列扣除 `d` 的组均值。两序列合并后的残差标准差为 `s`，自由度为受试者数减序列数。该受试者的内部学生化残差为组内偏差除以 `s * sqrt(1 - 1/n组)`。绝对值严格大于 2.5 时，把该受试者列入 `flagged_subjects`。该名单始终上报。异常只触发调查，保留两次原始观察。
3. 参比 CV 不超过 30% 时，`permission` 为 `cv_ineligible`，`gaps` 为空，固定界限 80%–125% 生效。超过 30% 时，核对每位被标记受试者的两个 R 样品。每个样品须能追溯到其分装、指定读数以及该读数所在批次的低、中、高三档质控。各档有编号 1 和 2 的两个槽位。包含边界在内，至少 4/6 个质控值相对标称值偏差在 ±15% 内，每档至少通过一个。批次合格后，该样品主测读数与复测读数的差的绝对值除以两者平均值须不超过 20%。本题用这个逐样品阈值触发调查。
4. 每个涉事样品只报当前能确定的第一项证据缺口，顺序为溯源、读数、质控槽位、批次合格性、读数相符性。多个缺失槽位全部列出。已齐全的批次若同时违反总数和某档门槛，分别列明。每条缺口均写为 `{"sample":样品号,"need":缺口种类,"record":应调取的记录}`。

| 情况 | `need` | `record` |
|---|---|---|
| 无法从样品找到分装 | `aliquot_trace` | 原样品号 |
| 没有该分装的指定复测读数 | `repeat_reading` | 分装号 |
| 缺少复测批次的一条质控原始记录 | `qc_record` | `批次号/level/replicate`，例如 `r7/mid/2` |
| 批次不合格，须有合格批次的复测 | `qualified_repeat` | `批次号/overall` 或 `批次号/low` 等 |
| 合格批次中复测与原样不符，须调查差异 | `investigate_difference` | 分装号 |

CV 超过 30% 且上述证据链完整时，`permission` 为 `permitted`。若筛查没有标记受试者，同样可放宽。若涉事证据缺失或矛盾，`permission` 为 `pending_evidence`，在 `gaps` 中逐一指出。未涉事受试者的旁支记录不阻断该判断。

## 给出论文可用的端点判断

`fixed_ok` 表示点估计与其整个区间落在 0.80–1.25 内。`if_permitted_ok` 表示在参比证据齐全的假设下是否支持。按方案，CV 超过 30% 时该区间界限为 `exp(±0.760 * min(sWR, sqrt(log(1 + 0.50²))))`。任何情形的点估计都必须在 0.80–1.25 内。端点值计入界限。`permission` 尚待核实且两种判断不一致时，`claim` 为 `needs_review`。两种判断一致时可报告共同结论。其余情形按获准的规则报告 `supported` 或 `not_supported`。

```json
{"n_subjects":24,"ratio":1.0,"ci_low":0.9,"ci_high":1.1,"reference_cv":0.2,"flagged_subjects":[],"permission":"cv_ineligible","fixed_ok":true,"if_permitted_ok":true,"claim":"supported","gaps":[]}
```

判卷器以 0.0001 的绝对容差核对数值，对证据缺口及标记名单按无重复集合精确核对。整题所有隐藏档案和重编码复核均正确时记 1。研究设计借鉴芬拉米多尔方案第 19.1.3 节，实验室质控限度取自 ICH M10 第 3.3.2 节。学生化残差 2.5、逐样品差异 20% 和上述处置流程属于本教学方案。[研究者原方案](https://cdn.clinicaltrials.gov/large-docs/69/NCT04639869/Prot_SAP_000.pdf) · [ICH M10](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-guideline-m10-bioanalytical-method-validation-step-5_en.pdf)
