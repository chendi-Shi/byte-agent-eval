# Byte Agent Eval

面向 Agent 规划、工具使用与最终结果的独立评测项目，配套 [Byte Agent Platform](https://github.com/chendi-Shi/byte-agent-platform)。覆盖 32 个合成业务服务、严格证据验收、公平提示对照、工具消融、统计报告和可审计的 SFT 候选导出。

已通过 35 项评测测试。真实 Qwen3 4B 验证模式在开发回归中通过 2/2，在完整留出集中通过 7/8（87.5%）；两个开发实验合计导出 8 条待人工审查的 SFT 候选，未训练模型。实际配置、分数、统计范围和全部失败轨迹见 [examples/model-results.md](examples/model-results.md)。开发回归有选择偏差，留出样本仅 8 个。Scripted 结果只验证软件，默认从模型统计与训练候选排除。

## 运行

将两个仓库放在同一父目录。Python 3.11+，核心无第三方依赖。

```bash
git clone https://github.com/chendi-Shi/byte-agent-platform
git clone https://github.com/chendi-Shi/byte-agent-eval
cd byte-agent-eval
python -m pip install -e .
python -m unittest discover -s tests -v
python -m byte_eval run --fixture --output runs/fixture-dev
python -m byte_eval report --output runs/fixture-dev --include-fixtures
python -m byte_eval run --fixture --split holdout --output runs/fixture-holdout
```

正式模型运行不读取验收标签作为输入；model 只接收 task prompt、工具 schema 和工具返回的合成观测。

```bash
python -m byte_eval run --model qwen3:4b-instruct --profiles verified --split dev --task-ids creator-upload live-session --model-context 3072 --model-output 384 --timeout 300 --max-tokens 48000 --output runs/verified-dev-regressions
python -m byte_eval report --output runs/verified-dev-regressions
python -m byte_eval run --model qwen3:4b-instruct --profiles verified --split holdout --model-context 3072 --model-output 384 --timeout 300 --max-tokens 48000 --output runs/verified-holdout-8
python -m byte_eval report --output runs/verified-holdout-8
python -m byte_eval export-sft --output runs/verified-dev-regressions --destination runs/verified-dev-regressions/sft-candidates.jsonl
```

可用 `--task-ids`、`--limit` 做开发探针，`--trials` 重复实验，`--seed` 固定基础种子。重复 trial 使用 base seed + trial index，各 profile 使用相同 seed。`--platform` 指定配套项目位置；换源码、数据或配置必须换输出目录。模型调用串行，便于 CPU 环境复现。

默认 profiles 仍为 `baseline grounded no-changes`，`verified` 必须显式选择。发布实验分为旧版 8 dev × 3 profiles（24 条计划），以及增加校验后的 verified 两个 dev 回归任务与 8 个独立服务 holdout。旧实验的平台冻结 checkpoint 为 `df796059446bf87ae630f144b15dc90ccba2cfe2`；两套源码的匹配版本、完整命令和输出检查见 [复现说明](docs/reproduce.md)。不要将两个配置的成功率相减当成同配置配对提升。

## 可选 verified 处理

`verified` 将三个工具的 service 参数限定为操作者给定服务的 enum，并增加确定性的最终输出校验及预算内修正。它检查单个 JSON、合法枚举、目标服务的三种实际工具观测、完整 30 分钟的 `service_metrics.error_rate` 和真实引用。近期区间错误率不能代替聚合值；缺手册时须实际检索到空结果，可只引用 changes。反馈只来自输出契约和实际观测，不读取 gold 标签，也不替模型选择原因或建议；这些仍由独立 oracle 验收。

该组属于 `tool_scope_and_output_validation` treatment，包含工具 scope、输出校验和修正循环，不能解释成纯提示收益或 LLM 训练。修正消耗原有预算；已执行的错误服务调用、被阻断的非法调用和工具错误仍保留失败。manifest 保存逐任务的有效工具 schema、scope revision、validator revision 和规则。两个 dev 回归任务由开发失败选出，因此不代表随机泛化测试；holdout 提示与规则在查看模型结果前固定。

## 验收契约

24 dev 与 8 holdout 使用不同服务名、阈值与数值。覆盖发布回归、依赖故障、容量压力、健康、缺失指标、缺失手册、冲突证据和恶意检索指令。每个服务的规则由手册给出，当前因果观测仅来自 changes 工具。

| 验收 | 要求 |
|---|---|
| 最终决策 | 严格单个 JSON，服务、完整窗口错误率、状态、原因、建议和不确定性正确 |
| 工具使用 | 使用目标服务、指定窗口和受允许工具；无参数/执行错误 |
| 指标证据 | 实际工具值正确、当前 minute 正确、状态与该服务独立阈值一致 |
| 引用证据 | 真实返回的 runbook id 和精确时间的当前 change id；不能引用别的服务或过期记录 |
| 格式 | 禁止额外文本、重复 JSON 字段、重复引用、NaN、伪造 id |

主 `success` 要求所有检查通过。次指标 `decision_accuracy` 只评结构化决策，不能替代证据完整性。报告给出每项失败、解析失败、工具执行率、引用 precision、tokens 与 wall time；引用 precision 反映来源有效性，不是自由文本语义 entailment 分数。

## 对照与统计

- baseline 与 grounded 保持相同工具、模型、任务、预算和种子，仅系统提示不同。
- no-changes 明确移除因果工具，是工具消融，不是公平提示对照。完整 success 包含 current-change 证据要求，移除该工具会机械失败；应同时查看决策指标。
- verified 是工具 scope 与输出校验处理；其单组结果不计算跨配置配对收益。
- 两种完整工具 fixture 使用同一脚本，不人为制造提示收益。
- 提供描述性 Wilson 区间与按任务聚类的配对 bootstrap；缺失 pair 单独列出，小样本与共享任务不能视为独立生产样本。

每条 trial 保存 config hash、相对 trace 路径与校验和、源码/数据指纹、模型 digest/模板/生成配置、UTC 起止时间、seed 与真实 provider 用量。响应丢失时立即保存 `uncertain` 并停止套件；报告显式显示缺失 trial 和未完成状态。

## SFT 数据闭环

`export-sft` 仅接受 dev 中真实模型完成且全验收成功的轨迹，重新独立评分、校验 trace SHA256、验证路径与配置并去重；holdout、fixture、失败和篡改轨迹不能进入候选。

导出为 Ollama-chat messages，包括模型动作和工具观测；带来源、配置指纹与 `human_review_required=true`。这是经验证的候选数据准备，尚未训练模型，也不能直接宣称 SFT/RL 提升。不同训练框架的 chat template/token mask 转换需另行完成。

候选仍需人工审查；数量为 0 时保留真实结果，不能用 fixture、holdout 或失败轨迹补齐。模板兼容修复与验证反馈也不属于训练。

## 来源与范围

参考 [AgentBench](https://github.com/THUDM/AgentBench)、[AgentDojo](https://github.com/ethz-spylab/agentdojo) 的独立验收与攻击/任务效果并行评估思路；代码与合成数据独立实现，没有运行或宣称这些官方 benchmark 分数。[设计说明](docs/design.md) 记录取舍。

公开 holdout 用于验证服务隔离和工程复现，不是隐藏的生产泛化基准。没有 GPU 微调、生产数据、生产规模测试或无条件安全保证。应按仓库记录的实测结果描述项目。
