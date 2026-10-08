# Byte Agent Eval

面向 Agent 工具调用、证据引用和最终任务结果的可审查评测流水线。直接驱动 [byte-agent-platform](https://github.com/chendi-Shi/byte-agent-platform)，由独立 oracle 验收结果，保存实验指纹、失败原因、配对统计，并导出可人工审核的 SFT 候选轨迹。

**状态：工程流程已验证；qwen3:4b 真实调用连续超时，尚无成功模型评测；SFT 训练和 Agentic RL 未执行。** 已提供 3 个 dev / 2 个 holdout 合成任务。公开可见的 holdout 仅用于流程隔离，不是秘密测试集。记录见 [examples/local-model-smoke.md](examples/local-model-smoke.md)。

## 复现

Python 3.11+。两个仓库放在同一父目录，在本仓库根目录运行：

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m byte_eval run --fixture --platform ../byte-agent-platform
python -m byte_eval report --include-fixtures
python -m byte_eval export-sft
```

离线无第三方运行依赖，也可设置 `PYTHONPATH=src`。PowerShell 用 `$env:PYTHONPATH='src'`。fixture 显示的是预设轨迹，不是模型表现；默认报告排除它，SFT 导出总是排除它。上面的 SFT 导出应得到 0 条。

已有本地 Ollama 工具模型时：

```bash
python -m byte_eval run --model YOUR_TOOL_CAPABLE_MODEL --trials 3 --output runs/model-dev
python -m byte_eval report --output runs/model-dev
python -m byte_eval export-sft --output runs/model-dev --destination runs/candidates.jsonl
python -m byte_eval run --model YOUR_TOOL_CAPABLE_MODEL --split holdout --output runs/model-holdout
```

不自动下载模型、不启动训练。运行前自动读取并记录模型 digest、量化与 Ollama 版本，硬件信息需要自行保存。遇到 uncertain 会停止后续任务并保存已有结果与 interrupted.json；报告明确显示未完成实验。更换运行环境后使用新输出目录，不自动重发丢失响应的请求。

## 开源参考与具体改进

GitHub 调研参考 [AgentBench](https://github.com/THUDM/AgentBench) 的函数调用环境与任务验收，以及 [AgentDojo](https://github.com/ethz-spylab/agentdojo) 的正常任务/攻击区分。本仓库为独立原创实现，没有移植其环境、数据集或成绩。具体协议与算法延伸见 [docs/evaluation-protocol.md](docs/evaluation-protocol.md)。

| 能力 | 当前实现 |
|---|---|
| Agentic Eval | oracle 检查正确服务指标、最终百分比、真实检索引用、完成状态与工具错误 |
| 策略对照 | 同模型、同工具、同任务、同预算；baseline 通用提示与 grounded 证据提示 |
| 失败归因 | 每项检查结果 + 首个失败原因；未知用量不等于免费 |
| 实验追溯 | 任务、知识文本、两套源码、提示、endpoint、预算指纹；变更后拒绝复用输出目录 |
| 统计 | Wilson 描述区间、按任务聚类 bootstrap 配对差值 |
| SFT 数据准备 | 只导出成功的真实模型 dev 轨迹，过滤 fixtures / failures / holdout，标记人工审核 |

Fixture 的 baseline 预设只查询指标，grounded 预设额外检索；这个差异是专门设计的流水线检查，不能用它宣称提示让模型从 0% 提升到 100%。真实运行时两组可用工具完全相同，仅系统提示不同。

## 输出

每个实验含 `experiment.json`、`results.json`、`summary.json` 和 `report.md`。每任务/重复/策略保留 SQLite journal 与 `trace.json`。默认 `runs/` 不进入 Git；公开示例报告见 [examples/fixture-report.md](examples/fixture-report.md)。`results.json` 的本地 trace_path 只用于本机导出，复制实验到别处时需要更新路径。

SFT 输出为 Ollama chat 消息结构，**不是某训练平台可直接提交的保证格式**。训练前需人工审核、去重、PII 清洗，并转换到所选训练框架的 tool-call 格式。自动验收只能证明狭窄的结构规则；不证明分析语义、因果结论或建议质量。

## JD 与项目边界

本项目能展示评测框架建设、规划/工具调用误差分析、可复现实验和 SFT 数据工程。没有训练 RL policy、没有执行 SFT、没有大规模分布式基准成绩；这些属于后续明确的验收阶段。面试时可以现场把一个回答引用改成不存在的 id，展示 oracle 如何拒绝 Agent 自报成功，再展示 fixture / holdout 不会进入训练样本。
