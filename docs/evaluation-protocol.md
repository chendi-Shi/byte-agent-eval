# 评测协议与训练延伸

## 微型任务套件

3 个 dev 和 2 个 holdout 任务全部使用合成服务指标和手写 runbook，服务与场景有重叠。它们用于验证系统，不代表泛化。任务要求查询指定服务、返回误差率百分比与来源引用。oracle 不读取 Agent 的“成功”宣称；它检查实际工具事件、数值和检索来源。

引用检查保证 id 出现在工具结果中、来源符合任务、没有未知 bracket 引用；不检查引用文本对最终结论的语义支持。工具 accuracy 表示“被注册且无执行错误的调用比例”，不是最优工具选择准确率。安全检查是是否尝试白名单外的工具，不是完整 prompt injection attack success rate。

## 对照

真实 baseline / grounded 使用相同模型、工具、知识、指标、预算与任务，差异为系统提示。grounded 显式要求证据、先取指标与 runbook、标注不确定性。fixture 两组使用不同预设轨迹，只测量报告是否正确；任何 fixture delta 都不构成模型提升。

按 `(task_id, trial, config_hash)` 配对。配置哈希包含两套源码、任务、知识、提示、模型名字、endpoint 与预算。变更任何这些内容时另开输出目录。还需手动冻结权重 digest 与运行环境，因为同名模型和 endpoint 可能变化。

报告保留首个失败原因及全部 checks；同一 task 的重复 trial 相关，bootstrap 的抽样单位是 task。Wilson 仅作描述，不能据此证明统计显著性。小任务集与重叠场景不能支持强泛化结论；正式实验应扩充任务、设置固定预算、预先记录指标和纳入规则。

## SFT / Agentic RL

当前只实现候选轨迹导出。必须来自 dev、真实模型且 oracle 通过，随后人工检查语义与数据质量。fixture 永不导出，holdout 永不导出；公开 holdout 无保密性，训练数据源必须另行防泄漏。

后续可以参考 [THUDM/AgentRL](https://github.com/THUDM/AgentRL) 构建工具环境的多轮 RL 实验，但本项目未集成该框架。先完成：

1. 建立独立且更丰富的任务结果 oracle，避免“说出期望数字”这样的奖励投机。
2. 固定环境与工具预算；奖励包含任务结果、允许工具约束与调用成本，记录每项奖励。
3. 按 SFT / SFT+RL 做同模型、同训练数据量的对照，测试集不参与提示/奖励调优。
4. 报告失败、拒答、工具错误率、token、每成功任务成本与延迟，保留原始轨迹。不能只报告成功率。

## 开源来源

2026-10-08 阅读 AgentBench README（blob `dce14d556dceb75d9c55e8e6196608d39ec92efc`）和 AgentDojo README（blob `81d78d00c68d614b9e3c40e1b4dad56d8c74ced1`）。只参考架构与评价设计，没有复制源码、任务、论文表格或实验结果。本仓库 MIT 许可证仅覆盖原创内容。
