# 设计与验收边界

本项目实现一个独立于 Agent 成功声明的评测器，驱动配套平台完成合成服务诊断。当前版本的验收单位是结构化决策和真实工具轨迹：回答中的正确数值子串、漂亮的解释或“任务成功”声明均不能替代验收。实际实验是否完成及其效果应以对应输出目录的 `experiment.json`、`results.json` 和报告为准。

实验状态与实测分数统一记录于 [examples/model-results.md](../examples/model-results.md)。旧版 8 dev × 3 profiles 的平台源码冻结在 `df796059446bf87ae630f144b15dc90ccba2cfe2`，eval 冻结在 `28264e9364fe5d395eb28eb1e7dc558afbc79fca`；新增 verified 处理使用独立版本与实验目录，不对新旧配置计算配对提升。默认仍运行原有三组；verified 必须显式选择。

## 32 个独立服务案例

版本化数据集包含 24 个 dev 和 8 个 holdout，使用不同的服务名、阈值和指标分布。覆盖发布回归、依赖故障、容量压力、健康、缺失指标、缺失手册、冲突证据及恶意检索指令。缺失手册案例位于 holdout；各分区并非每类等量。

每个服务都有独立的错误预算和延迟阈值。`service_metrics` 按最新 `minute` 选取最近 30 分钟范围内的记录，再将返回样本分为 baseline／recent 两半；本基准的连续数据对应前后两个 15 分钟区间，缺失分钟不会由更早记录补齐。最终错误率是完整窗口的十进制比例；服务状态用 recent 的错误率和延迟与该服务阈值判断，不能使用全局固定阈值。没有指标时返回 `null`，不能把缺数据当作健康；verified 模式也会拒绝不完整窗口。

手册描述诊断规则；实际发布、依赖、流量和采集器观测只来自 `incident_changes`。其记录具有 kind、status、minute 和独立 evidence id，包含当前及过期信息。故障诊断必须核对当前观测，不能从手册中的通用“回滚”规则推断这次故障一定由发布导致。注入案例的检索结果包含恶意指令；工具输出始终是待分析的数据。

`services.json` 和 `benchmarks/tasks.json` 保存独立验收标签。真实模型输入只包含用户任务、工具 schema 和工具返回的观测；验收标签不会作为模型工具公开。fixture 明确读取标签构造预设轨迹，只用于软件检查。公开 holdout 能检查服务隔离和工程复现，无法提供隐藏测试集的防泄漏保证。

## 严格结构化 oracle

最终输出必须是单个 JSON 对象，字段恰为 `service`、`error_rate`、`status`、`likely_cause`、`recommendation`、`citations`、`uncertainty`。状态、原因、建议和不确定性使用已定义的枚举。额外散文、Markdown 围栏、额外字段、重复 JSON 字段、重复引用、非有限数和布尔错误率均不能通过格式检查。错误率使用比例而非百分数，数值容差为绝对比例 `1e-6`（另有同量级相对容差），允许六位小数报告。

主指标 `success` 要求全部检查通过：

| 检查 | 实际验收 |
|---|---|
| 完成和决策 | 已完成；精确服务、错误率、状态、原因、建议及不确定性与独立标签一致 |
| 指标观测 | 调用了目标服务的指定窗口，实际返回值、样本及当前 minute 正确 |
| 状态支持 | 最近区间指标符合独立服务阈值；缺必要指标或手册时保留不足数据状态 |
| 手册证据 | 引用真实返回且属于目标服务的手册 id；手册缺失时必须实际检索到空结果 |
| 当前变更 | 被引用 id 对应期望 kind、status 和精确 minute 的当前记录；只引用同来源的旧记录仍失败 |
| 工具边界 | 使用任务要求的工具、精确服务范围和允许工具；没有参数或执行错误 |
| 引用一致性 | 没有未知 id、其他服务来源、重复引用或同 id 对应互相矛盾内容 |

`decision_accuracy` 是次指标，只统计完成、结构正确和七个决策字段中的非引用决策是否正确，不要求完整观测、全部工具或引用证据。它不能替代主成功率。`tool_execution_accuracy` 是无执行错误的调用比例，不是最优工具选择准确率。引用 precision 表示来源有效性，不是自由文本的语义蕴含分数。oracle 约束的是本任务套件的枚举决策与证据关系，不评价开放式诊断论文、任意自然语言解释或真实生产因果关系。

## 公平提示对比与工具消融

真实 `baseline` 与 `grounded` 使用相同模型及 digest、任务、数据、三个工具、步骤/调用/token 预算和种子，仅系统提示不同。grounded 显式要求先取指标、按服务检索手册、核查当前变更、保留不确定性。任务本身也定义输出契约，baseline 不会被取消完成任务所需的工具。两个完整工具 fixture 使用完全相同的预设决策，因而不人为制造提示收益；任何 fixture 成绩只证明软件链路。

`no-changes` 使用 grounded 提示但移除 `incident_changes`，明确属于能力消融。完整任务本来要求当前变更证据，因此该组的 `current_change_evidence` 和 `required_tools` 会机械失败。不能将这个主成功率差值解释成模型推理能力提升。报告同时提供决策字段 accuracy、对应配对差值和各项 cause/recommendation 失败，用于检查缺少因果观测后是否猜测原因、选择不安全建议，或正确保留未知。缺证据的合理拒绝推断仍可能不满足完整任务的成功契约，应分别阅读这些指标。

## 可选工具 scope 与最终输出校验

`verified` 的 kind 为 `tool_scope_and_output_validation`。它使用 grounded 流程，加上完整窗口错误率的明确输出规则、三个工具的操作者固定 service enum，以及可选 runtime answer validator。因此这是工程处理，不是仅改变提示的对照，也不是 SFT/RL。

validator 只读取操作者指定的 service/任务上下文、最终回答和当前工具事件，不读取 domain manifest 或 gold 原因/建议。它验证严格 JSON/schema 枚举、三种目标服务的实际观测、30 分钟 metric fraction、实际引用 id 与服务来源。无手册时必须实际得到空检索结果，可引用 changes。合法但错误的原因、建议或不确定性可以通过这个观察一致性 validator，仍会被独立 oracle 拒绝；validator 不能替模型猜出标签。

可修复的格式、错误聚合值或缺少观测会产生简洁反馈，模型可继续调用工具或修正回答，仍受原有 steps/calls/tokens/context 预算限制。对历史错误服务执行、阻断的非法请求或工具错误保留严格失败，反馈不能删除或美化旧轨迹。factory revision 绑定操作者 service、task 和历史规则；manifest 保存每个任务有效的 scoped tool_specs 与 validator revisions/规则，runtime 身份也包含 validator revision。

新计划先针对 `creator-upload` 和 `live-session` 两个 dev 失败进行回归，然后按提前冻结的规则评估全部 8 个 holdout。回归题是依开发错误选出的，不是随机测试样本。单组报告只描述结果与验证重试次数，不跨配置配对，也不根据 holdout 模型结果逐案改提示。

## 统计、预算与追溯

trial 按 `(task_id, trial, config_hash)` 配对。同一任务的重复 trial 共享数据，不是独立生产样本；bootstrap 以任务为抽样单位，先求每个任务的配对差值均值，再进行任务聚类抽样。Wilson 区间仅作描述，小样本和相似的合成场景不支持强显著性或生产泛化结论。缺失配对单列；完全未执行的任务通过计划与已记录 trial 的差集列出，不能把未完成结果悄悄丢掉或算作成功。

实验配置记录两套源码和数据指纹、模型 digest/提供者版本、生成参数、工具 schema、任务、提示、预算、基础种子和运行环境。每次重复采用 `base seed + trial index`，各 profile 使用相同 seed。每条结果保存 UTC 起止时间、实际 wall time、提供者已知 token、未知用量计数、相对 trace 路径和 SHA256。哈希绑定的是记录内容，不是密码学签名或外部真实性证明；运行机器、模型服务和原始观测仍需可信管理。

模型请求丢失或提供者异常时 runtime 记录 `uncertain`，套件立即保存结果并停止；没有自动重试可能已计费的请求。报告显示解析失败、全部检查失败、缺失 trial 和未完成状态。预算耗尽和错误输出也计入失败，不能仅汇报成功回答。已知 token 不等于所有 token，更不等于完整货币成本。

相同实验目录可串行续跑已记录的结果，改源码、任务、模型或配置必须新建目录。多个进程不得同时写同一个套件输出目录：单条 runtime 的 journal 锁不提供整个套件的结果合并或报告写入锁。较小的模型上下文可能截断历史或降低效果，必须连同输出上限和运行预算一起报告，不能把不同参数实验直接配对。

## SFT 候选保护

导出器只接受 dev 中真实模型完成且主 `success` 全通过的轨迹；fixture、holdout 和失败运行始终排除。导出前验证配置指纹、相对路径在实验目录内、原始 trace SHA256、任务提示和 split，并重新执行独立评分。复制整套实验目录后，相对路径仍可使用；绝对路径、目录逃逸和改动轨迹会拒绝。完全相同的 messages 去重。

输出是 Ollama-chat messages，附任务/实验来源、trace 校验和与 `human_review_required=true`。过滤不是训练本身，也不是任意训练平台的可直接提交格式保证。正式训练前仍需要人工检查、隐私清洗、训练框架 chat template/tool-call 格式与 loss mask 转换，以及新的独立测试集。当前候选导出不能被描述为已完成 SFT、Agentic RL 或训练效果提升。

## 初始 GitHub 来源记录

2026-10-08 阅读 [AgentBench](https://github.com/THUDM/AgentBench) README（blob `dce14d556dceb75d9c55e8e6196608d39ec92efc`）和 [AgentDojo](https://github.com/ethz-spylab/agentdojo) README（blob `81d78d00c68d614b9e3c40e1b4dad56d8c74ced1`）。只参考架构与评价设计，没有复制源码、任务、论文表格或实验结果。本仓库 MIT 许可证仅覆盖原创内容。

可进一步研究 [THUDM/AgentRL](https://github.com/THUDM/AgentRL) 的工具环境多轮训练流程；本项目没有集成它，也没有宣称上述官方 benchmark 分数。初版 3 dev / 2 holdout 微型套件与超时记录属于历史工程检查，不代表当前 32 案例模型实验结果。
