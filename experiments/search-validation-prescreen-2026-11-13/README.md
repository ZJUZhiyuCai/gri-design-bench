# 搜索与验证预算的无模型预筛

2026-11-13。本次用户授权范围：实现并运行带验证的强基线、固定策略对照和必要消融，判断是否值得进一步研究。禁止发布；不添加 Claude 或任何 AI 为 contributor。

本研究只新增文件，原 v0.2 程序、实例、结果保持不变。`plan.json` 和 `implementation-lock.json` 在第一次正式搜索前本地冻结，计划 SHA-256 为 `b4d12b6312c0d9c0237a86389ca8bdcad55c024aea34c4a9a0b46b9b47723211`。这是本地事前记录，不声称独立托管预注册。

## 比较安排

六个已见开发实例，18 名互不重叠的虚拟患者；每个随机方法五个优化器种子。每例使用新的32种子评测面板，前16个为主指标，全部32个为敏感性检查。模型不参与本轮。

一个查询单位为一份设计 × 一个进餐种子 × 三患者 × 三变体，即九条三天轨迹。主要在线方法各有256查询单位；另行记录CPU，不直接与历史30 CPU秒模型榜比较。

| 方法 | 查询分配 | 用途 |
|---|---|---|
| de_search | 128候选 × 2训练种子 | 更多候选搜索 |
| de_fixed | 64候选 × 2训练种子；8入围 × 16新种子 | 固定验证分配 |
| de_racing | 同一64候选；8×4、4×8、2×32追加验证 | 根据结果逐级淘汰；保持零释放后备 |
| sobol_fixed | 同预算Sobol候选＋固定验证 | 替代优化器控制 |
| constant_search | 恒速二维设计，128候选 × 2种子 | 恒速搜索对照 |
| constant_fixed | 恒速二维设计，64候选＋固定验证 | 较强恒速对照 |
| de_no_margin | 与de_fixed完全相同观测，选择用正式门槛 | 验证安全余量消融 |
| de_early | 同一候选前缀直接选训练最优，128查询 | 半预算检查点，不能称等预算 |
| fixed_transfer | 其他五例历史精修参数中位数，裁剪到目标边界 | 排除目标设计的固定迁移；历史训练成本不为零 |

总计246条方法输出（8个在线/消融方法 × 6实例 × 5重复＋6个固定迁移）。共享确定性的候选前缀节省重复计算；每个方法的查询账本仍按单独运行所需预算计，不借用后续搜索发现的候选。

DE实现为有明确配置的顺序DE/rand/1/bin，不是与旧v0.2 CPU基线字节相同的复跑。两者不能当作同一方法跨版本成绩。

## 预先冻结的决策

- 固定验证相对纯搜索：平均分提高至少5个百分点、六例中至少四例方向为正，安全通过数最多少1/30，才进入完整原生确认。
- 自适应验证相对固定验证：平均分提高至少3个百分点、至少四例为正且安全通过数不降低，才值得继续研究这一自适应策略。
- 固定迁移距最佳响应式在线方法不超过5个百分点且至少5/6例通过时，提示任务可能不需要复杂逐例搜索。此门槛不构成等效性检验。
- 全部结果先由RK4筛查；每个唯一设计的第一个评测种子（九轨迹）及所有接近安全门槛的轨迹，使用原生dopri5复核；六例各有一条原始生理RHS对照。
- 若固定验证达到门槛且抽检没有安全分类差异，完整原生复评 de_search/de_fixed 的全部主面板。任何未完整复评的方法继续标为筛查证据。

规则不因方向是否有利而调整。不显著不等于等效；重复次数不增加独立患者组数；已见开发患者组不能冒充外部患者验证。

## 本机复现

在仓库根目录按[主 README](../../README.zh-CN.md#复现)安装项目。脚本拒绝覆盖结果；相同冻结配置可以续跑缺失工作，但不覆盖或替换已有完成记录。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  .venv/bin/python -I -m gri_bench.prescreen_v03.run search --workers 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  .venv/bin/python -I -m gri_bench.prescreen_v03.run screen --workers 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  .venv/bin/python -I -m gri_bench.prescreen_v03.run audit --workers 3
.venv/bin/python -I -m gri_bench.prescreen_v03.analyze \
  --output private/search-validation-prescreen-reproduction
.venv/bin/python -I -m gri_bench.prescreen_v03.run preserve
```

若固定门槛通过，再运行 `run confirm`，并用新的报告输出目录重做分析。程序自身检查门槛，不以手工改结果触发。

源码在 `src/gri_bench/prescreen_v03/`；完整运行证据在 `private/search-validation-prescreen-2026-11-13/`，不进入既有结果目录。正式运行前52项回归通过（含新增8项），仅有既存依赖弃用警告。

## 执行结果与补充复算

本轮已完成，见[结果报告](../../results/search-validation-prescreen-2026-11-13/README.md)与[论文价值判断](../../results/search-validation-prescreen-2026-11-13/CONCLUSION.md)。三个策略改善／迁移筛选门槛均未通过；数值复核通过，未触发完整主要比较原生确认，也未启动新Agent实验。

运行证据还包括：

- `scripts/audit_prescreen_selection.py`：搜索完成、开启评测前独立核对选择与查询账本，输出保存在私有运行目录。
- `scripts/prescreen_reference_diagnostic.py`：运行前另记的六个历史高预算参考设计，使用相同新面板；此诊断不影响主要决策门槛。
- `scripts/audit_prescreen_scores.py --output <新文件>`：从保存的数组与逐轨迹指标独立复算所有分数。
- `scripts/analyze_prescreen_mechanisms.py --output <新文件>`：事后描述方法选取相同设计的次数及实例异质性，不运行新搜索。
- `scripts/plot_prescreen_results.py <新报告目录>`：读取完整结果表绘制科学图；PNG已逐张检查，同时保留SVG。

脚本路径相对于仓库根目录，使用 `.venv/bin/python -I` 运行。派生文件拒绝覆盖，复算应指定新的输出位置。

**并发工作区说明：** 数值报告生成后，另一项v0.2九模型任务提交`1a23868`，只修改受保护列表中的两份主README并新增其结果。冻结代码、实例和既有数值结果未变。该记录对应本轮预筛结束时的工作区。原`run preserve`及`analyze`中的严格全文件检查现在会如实报告这两项变化，没有修改校验规则来掩盖它们。见[精确哈希与Git差异记录](../../results/search-validation-prescreen-2026-11-13/workspace-concurrency.json)。若重跑需要严格对照冻结清单，应在独立副本中使用原提交`b8fc260`的两份README，复制本轮新增代码与证据；不要回退共享工作区的并行成果。独立数值复算脚本仍可直接对现有保存证据运行。
