# GRI Design Bench

[English](README.md) · 简体中文

GRI Design Bench 以葡萄糖响应胰岛素（GRI）释药为例，评估 Agent 能否在终端完成有对照的药学模拟，并交出可独立复算的结果。释药时序任务研究每日胰岛素释放量相同的情况下，改变日内释放时序会怎样影响模拟血糖。

| 任务或研究 | 内容 | 当前进度 | 入口 |
|---|---|---|---|
| 释药时序归因 | 本地 Harbor 原型：构造等日剂量对照并复现 54 行结果 | 四次本地验收测试，待开展 Agent 试测 | [Harbor 原型](harbor/release-timing-attribution/README.md) |
| 时序实验 | 作者按同一对照运行的干实验，共 216 个配对情景 | 已完成作者实验 | [时序实验](results/timing-study-2026-11-13/README.md) |
| v0.2 设计任务 | 固定计算预算下搜索配方，用新进餐情景评分 | 9 条路由，324 次尝试 | [九模型报告](results/v0.2/expansion-2026-11-13/README.md) |
| 材料验证诊断 | 在 24 个模拟状态上，追加哪项测量会改变候选去留 | 已完成基线比较 | [材料验证](results/material-validation-2026-11-13/README.md) |

[科学定位](docs/SCIENTIFIC_SCOPE.md) · [测什么能力与研究闭环](docs/RESEARCH_LOOP.md) · [材料边界来源](docs/BOUND_PROVENANCE.md)

## 为什么先做 GRI

响应释药与匀速释药的差异可能来自每一天的释放量，也可能来自一天内何时释放。在仿真中，可以固定虚拟患者、进餐、初始状态和每一天的释放量，只改变日内时序。

GRI 有药代建模先例，也有可约束部分释放参数的体外数据。先选它，是因为逐日等量这个科学约束能逐行验证。配对结果可以显示效应在哪些条件下出现和减弱，供研究者判断下一步该补哪项证据。 [Bakh 等，2017](https://pubmed.ncbi.nlm.nih.gov/28841775/) · [Xu 等，2025](https://pubmed.ncbi.nlm.nih.gov/40011600/)

相关项目还有一道生长激素节律贴片题，用论文中的实测血浆浓度推断有效时序，再预测三条曲线各自留出的尾段。贴片题考从实测数据做推断，GRI 首题考能否把对照实验做对并复现。 [Han 等，2025](https://pubmed.ncbi.nlm.nih.gov/40181125/)

## 释药时序归因

任务给定 `dev-06` 的一份配方和三名虚拟患者。每名患者使用两个进餐种子，分别模拟正常进餐、漏午餐和大份晚餐。Agent 对每个情景运行三组模拟。

1. 模拟原始的葡萄糖响应释放轨迹。
2. 第一天沿用原释放轨迹，第 2、3 天分别把当天的释放量均匀分布到当天。
3. 第一天沿用原释放轨迹，第 2、3 天分别将当天的释放曲线循环平移 12 小时。

两个对照用全天的响应轨迹做事后回放，用于检验时序的作用。三组模拟以第一天为共同预热。

Agent 将 54 行结果写入 `/app/output/results.json`（3 名患者 × 2 个种子 × 3 类进餐 × 3 组模拟）。每行包含释放轨迹、每日剂量、目标血糖范围内时间（TIR，70–180 mg/dL）、低于 70 和 54 mg/dL 的时间及最低血糖。时间比例用第 2、3 天计算，最低血糖取三天全程。文件还记录响应组相对两种对照的平均配对差。 [任务说明](harbor/release-timing-attribution/instruction.md)

独立 Docker 容器内的验收器核对情景覆盖、释放轨迹、逐日剂量、共同预热、对照定义、血糖指标和配对差。参考值使用原始 `simglucose` 生理方程及原生 dopri5 独立生成。结果在数值容差内即可通过，包括响应组表现较差的情景。

| 验收测试用例 | 结果 |
|---|---:|
| 原生正确解 | 1 |
| RK4 释放求解加原生回放 | 1 |
| 空提交 | 0 |
| 跨两天合并匀速的错解 | 0 |

最后一个控制的三天总剂量几乎不变，但某一天的剂量相差 0.554 U，会把“量”和“时序”混在一起。 [控制记录](results/timing-study-2026-11-13/harbor-verification.json)

任务直接给出对照方案，考查 Agent 能否执行并复现这段科研分析。本地原型采用 Terminal-Bench-Science 的容器化和程序化验收方式，Agent 难度和上游收录资格仍待评估。 [Terminal-Bench-Science 任务要求](https://www.terminal-bench-science.ai/contribute)

## 作者运行的时序实验

作者把同样的对照用于六个公开开发组的固定设计。216 个配对进餐情景来自 18 名已见过的虚拟患者。Harbor 原型使用另一组更小的输入。

相对逐日等量的匀速对照，响应组的平均 TIR **高 5.82 个百分点**，低于 70 mg/dL 的时间平均**少 3.74 个百分点**。六组的 TIR 增益为 0.55 至 12.30 个百分点，部分情景没有增益。

[计划](results/timing-study-2026-11-13/plan.json) · [摘要](results/timing-study-2026-11-13/summary.json) · [逐情景结果](results/timing-study-2026-11-13/outcomes.json)

### 从产物到论文证据

| 论文部分 | 产物提供什么 |
|---|---|
| 方法 | 仿真开始前记录的运行计划，包括三组模拟、共同预热、逐日等量及分析窗口 |
| 主图 | 各组的配对差，可由逐情景表重算 |
| 补充材料 | 完整的逐情景表（含未改善的情景），以及输入和脚本版本 |
| 结论 | 限于该仿真模型和这六组固定设计 |

验收器检查提交的 JSON。把 Agent 的分析写进论文前，还需要审查代码及数据来源，并独立重跑。需要补多少独立证据，取决于论文的具体主张。要验证 Agent 能否节省科研工时，可在相同的留出输入、仿真预算和验收标准下，与现有固定脚本比较，记录研究人员准备、核查和返工的时间。

## v0.2 设计任务

[![v0.2 设计任务：固定配方随葡萄糖变化调节释放。Agent 测试和提交候选方案，独立评测器用 144 条轨迹计算最终得分。](docs/assets/benchmark-overview-v02-zh-CN.png)](docs/assets/benchmark-overview-v02-zh-CN.svg)

Agent 获得三名虚拟患者、材料边界和两个训练进餐种子，累计有 30 CPU 秒用于搜索响应式或恒速释放配方。最后一次经 `submit_design` 接受的合法配方用于评分。三名患者共享配方参数，释放强度和储量按个体的参考日胰岛素量缩放。

| 响应式配方参数 | 决定什么 |
|---|---|
| `theta_a` | 整体释放强度 |
| `relative_leak` | 葡萄糖响应很弱时的基础释放 |
| `ec50_mg_dl` | 响应部分达到最大值一半时的葡萄糖浓度 |
| `hill_n` | 释放量在响应中点附近上升的陡峭程度 |
| `tau_min` | 配方跟随组织液葡萄糖变化的速度 |
| `theta_L` | 储库里可释放的胰岛素总量 |

评测器用原生 dopri5 重跑 144 条三天轨迹（3 名患者 × 16 个新进餐种子 × 3 类进餐）。每条轨迹都要满足三项仿真低血糖约束。

- 第 2、3 天低于 70 mg/dL 的时间不超过 4%。
- 第 2、3 天低于 54 mg/dL 的时间不超过 1%。
- 三天内每分钟采样的最低血糖不低于 40 mg/dL。

通过后，得分为第 2、3 天的平均 TIR。缺少合法提交、仿真失败、未通过低血糖约束或超出资源限制的尝试记零分。 [v0.2 评测规则](docs/v02/PROTOCOL.md) · [释放模型](src/gri_bench/release.py)

九条 Magpie 路由在 6 个开发实例和 6 个封存实例上各重复 3 次，共 324 次尝试。24 次固定优化器基线使用同样的搜索 CPU 预算。封存实例使用同一公开虚拟患者池的新组合和新进餐情景。每条路由在封存集上有 18 次尝试。

| 路由或基线 | 合法提交 | 通过血糖约束 | 平均分（%） |
|---|---:|---:|---:|
| GPT-6.1 Sol（最高） | 18/18 | 18/18 | 73.11 |
| Intern-S2（最低） | 3/18 | 2/18 | 8.20 |
| 响应式基线 | | | 58.03 |
| 恒速基线 | | | 49.48 |

封存集三轮排名两两比较的 Kendall τ-b 为 0.67–0.83，36 对路由中有 7 对至少反转过一次。端到端得分受工具使用、搜索、预算管理和提交质量等因素影响。完整报告还提供开发集结果和失败分类。

[九模型报告与完整榜单](results/v0.2/expansion-2026-11-13/README.md) · [首批三模型](results/v0.2/sealed/README.md) · [校准和长预算搜索](results/v0.2/calibration/README.md)

## 追加哪项证据会改变候选去留？

这项实验比较追加哪项测量能帮助研究者决定候选是否值得继续表征。六个候选组各有四种模拟材料状态，使用另一批进餐情景复核判断。

- 固定验证基础泄漏，使判定与参考一致的状态从 22/24 提高到 24/24，找回两个漏选的状态。
- 固定验证响应延迟，仍为 22/24。
- 逐例选择测项时，在这些输入上选的是同一测项，结果与固定测泄漏相同。

测量是理想化的模拟查询。逐例和固定测基础泄漏所得判断相同，本轮止于基线比较。下一步优先取得低糖条件下的释放曲线和剩余储量实测数据。 [研究闭环](docs/RESEARCH_LOOP.md) · [材料验证研究](results/material-validation-2026-11-13/README.md)

## 依据与边界

- **释放模型。** 部分释放形状来自对 Xu 等论文中包膜胰岛素晶体体外曲线的历史拟合。原材料同时响应葡萄糖和 β-羟基丁酸。本项目使用葡萄糖单输入、有限储库的简化模型，扩展了拟合边界，并单独设定剂量与装量约束。 [边界来源](docs/BOUND_PROVENANCE.md)
- **生理模型。** 使用含 30 名虚拟患者的开源研究实现 `simglucose 0.2.11`，叠加项目的释药模型和三天多餐协议。生理方程未纳入低血糖反调节。 [simglucose](https://github.com/jxx123/simglucose)
- **监管先例。** 2008 年 FDA 接受原版 UVA/Padova 1 型糖尿病仿真系统，在人工胰腺闭环控制策略的特定临床前测试中替代动物试验。原开发者说明，验证和接受限于单餐情景。本项目的三天协议用于模型内研究，材料可实现性、临床安全和疗效均需另外取证。 [Kovatchev 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC2681269/) · [Dalla Man 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC4454102/)

## 复现

在仓库根目录用 Python 3.12 安装项目。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install setuptools==80.10.2 wheel==0.48.0
.venv/bin/python -m pip install --no-build-isolation -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
```

安装项目后，可直接在 Python 环境中重跑时序实验。每次指定一个新的输出目录。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  .venv/bin/python -I scripts/run_timing_study.py --output private/my-timing-study
```

运行 v0.2 开发实例还需要 `curl` 及支持 cgroup v2 的 Docker。把 `gri_docker_context` 改为正在运行的 Docker context 名称。

```bash
gri_docker_context=default
docker --context "$gri_docker_context" build -t gri-bench:0.1.1 .
docker --context "$gri_docker_context" build -f Dockerfile.v02 -t gri-bench:0.2.0 .
.venv/bin/python -m gri_bench.v02.matrix --context "$gri_docker_context" \
  --case dev-01 --output private/my-baseline
```

这条命令运行固定响应式基线，无需模型账号。要在同一实例上运行 Agent，加入 `--model YOUR_ROUTE` 并另选一个输出目录。运行器读取 `GRI_MODEL_BASE_URL`（默认 `http://127.0.0.1:3425/v1`）和可选的 `GRI_MODEL_API_KEY`，把提交设计、运行记录和原生评测分数保存到输出目录。

Harbor 任务的构建和离线控制运行说明见[其 README](harbor/release-timing-attribution/README.md)。

[开发实例](instances/dev/) · [评测种子](instances/v0.2/development-evaluation.json) · [开发试测注册计划](contract/v0.2/development-plan.json) · [封存实例哈希承诺](contract/v0.2/sealed-manifest.json)

v0.1.1 归档记录了按更早协议运行的另一组九路由、324 次对比。 [v0.1.1 归档](https://github.com/ZJUZhiyuCai/gri-design-bench/tree/31b8731f927691ccb4ed46064d3974dd5bf55373) · [MIT 许可证](LICENSE) · [第三方声明](THIRD_PARTY_NOTICES.md)
