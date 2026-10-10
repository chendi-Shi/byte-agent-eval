# 两个项目干了什么，怎么做

这两个仓库把岗位中的 Agent 平台、工具与知识接入、Agentic Eval、SFT
和 Agentic RL 串成了一个能检查代码与实验记录的研发诊断场景。平台负责
执行，评测项目负责独立验收，再用小模型训练实验验证参数优化流程。

## 先把业务任务变成可验收的问题

场景是工程师询问“某服务当前是否异常，可能原因是什么，下一步该做什么”。
不能只让模型写一段看起来合理的解释。我设计了 32 个虚构服务事件：
24 个开发案例、8 个公开留出案例，覆盖发布回归、依赖故障、容量压力、
健康、缺指标、缺运行手册、冲突证据和恶意检索指令。

每个服务都有自己的错误率和延迟阈值。运行手册提供规则，SQLite 提供
当前指标以及发布、依赖、流量和采集器变化。诊断要查自己的手册，使用
最近 30 分钟的完整错误率，比较近期指标与服务阈值，并引用实际返回的
当前证据。没有指标或手册时要承认数据不足，不能借用另一个服务的阈值。

GitHub 调研参考了 [AgentBench](https://github.com/THUDM/AgentBench) 的
任务验收思路和 [AgentDojo](https://github.com/ethz-spylab/agentdojo) 对任务
效果及不可信内容的处理。两个项目的代码、业务数据与结果独立实现；
没有把这些官方 benchmark 的分数当成自己的实验分数。来源与取舍见
[设计说明](design.md)。

## 项目一：让 Agent 真正调用工具并保留执行证据

[byte-agent-platform](https://github.com/chendi-Shi/byte-agent-platform)
实现 ReAct 循环：模型选择动作，平台验证参数，执行工具，将 observation
返回给模型，再决定继续还是输出最终答案。三个工具分别读取服务指标、
检索服务运行手册、查询当前变化记录。工具使用参数化 SQL 和精确服务
过滤，执行范围是只读诊断。

例如诊断 `live-session` 时，Agent 先调用 `service_metrics` 取 30 分钟
指标，再以相同 service 调用 `knowledge_search`，最后调用
`incident_changes` 核对当前依赖及发布记录。它必须区分“手册建议检查
发布”和“当前证据显示发布导致故障”；模型推荐回滚审查不等于执行回滚。

知识库按 Markdown 段落分块，引用 ID 绑定来源、位置和内容。BM25 负责
词项检索，可选 Embedding 提供语义检索，两者用 RRF 合并排序。查询绑定
服务和来源，索引替换有事务保护。MCP 使用官方 SDK 的服务与客户端完成
初始化、工具发现和调用；Skill 是操作者显式选择的可信工作流，检索文本
始终作为证据处理。执行记忆保存消息、工具计划和结果，主要用于恢复与
审计。

工程上的重点是失败处理。每条运行有步骤、调用和 token 预算，实际轨迹
保存在 journal 与 `trace.json` 中。模型响应丢失时记录 `uncertain` 并停止
自动重发；可重放的只读工具与可能已经发出的模型请求使用不同恢复规则。
任务队列通过幂等键、租约、心跳和 fencing token 避免重复提交及过期 worker
写回。扩展的编排和跨进程运行设计可分别查看平台的
[Multi-Agent 说明](https://github.com/chendi-Shi/byte-agent-platform/blob/main/docs/multiagent.md)
与[分布式执行说明](https://github.com/chendi-Shi/byte-agent-platform/blob/main/docs/distributed.md)，
实测范围以对应报告为准。
新增的真实协作和网络 worker 记录统一指向平台的
[V3 实测记录](https://github.com/chendi-Shi/byte-agent-platform/blob/main/examples/v3-results.md)，
不从源码或软件 fixture 推断模型任务已经成功。

四角色 V6 从原始工具事件重算数据可用性、前后样本数与每观测样本
的请求数，避免把角色权限误当作全局缺值，或把整个窗口的请求数误当作
近期增长。它还检查真实手册、完整指标及未截断变更能够直接验证的容量
判断矛盾；修正反馈只给实际观测，不给替代原因或 gold。该数值不假定
采样间隔，不能称为 RPS。这属于执行中的观测一致性处理，最终业务效果
仍看独立 oracle。源码来源见
[V6 元数据](../examples/acceptance-source-v6.json)。

后续 V7 将引用选择绑定到实际成功观测中的 ID，避免审查者反复将工具名
`service_metrics` 当作未观测引用而耗尽修复预算。可用引用列表与原始观测一同封存，模型仍需判断
哪些证据支持其原因与建议；Schema 不提供 gold、正确原因或数值答案。
审查者不同意某个提议会触发重新判断，不会自动伪造专家之间的事实冲突。
来源见 [V7 元数据](../examples/acceptance-source-v7.json)；之前失败的开发运行
与后来运行一起保留，不将开发重试后的通过解释成随机留出准确率。

V7 实际执行中四个角色都已 completed，引用、Schema 和共享观测协议通过，
但六个业务字段仅服务、整窗错误率和 incident 状态三项正确；最终保守地
选择证据不足、继续收集与数据缺失，整体验收失败。七轮开发尝试全部保留，
没有再针对同一案例改提示追求通过。见平台的
[V7 负面结果](https://github.com/chendi-Shi/byte-agent-platform/blob/main/examples/experiments/multiagent-v3-compact/report.json)。
另一条真实 TCP worker 的 `creator-upload` 开发任务通过独立 oracle；
[Ubuntu 容器 CI](https://github.com/chendi-Shi/byte-agent-platform/actions/runs/37918991758)
完成 12/12 条数值夹具，两者与 Multi-Agent 的语义失败分别记录。
容器实验启动两个 worker，但全部任务实际由同一个 worker 完成，
[原始容器报告](https://github.com/chendi-Shi/byte-agent-platform/blob/main/examples/experiments/container-ci-v3/report.json)
不支持公平调度或并行提速结论。

## 项目二：模型说成功，评测器仍要自己检查

`byte-agent-eval` 的 oracle 不接受 Agent 的“完成”声明。它检查严格 JSON
字段和枚举、目标服务、完整窗口数值、实际工具事件、当前指标、引用 ID、
证据来源及当前变化的 kind/status/minute。最终 `success` 要求全部检查
通过；只猜对状态或原因的 `decision_accuracy` 单列，不能替代成功率。

对照实验让 `baseline` 与 `grounded` 使用相同模型、工具、任务、种子和
预算，仅改变系统提示。工具消融 `no-changes` 则取消变化查询，观察缺少
因果证据时的决策表现。消融缺工具会直接违反完整证据契约，因此报告
同时给出次级决策准确率，不能把必然的完整性差值解释为推理能力提升。

后来增加的 `verified` 是工程处理：操作者固定 service scope，validator
检查实际观测与输出契约，并允许在原预算内纠正格式或观测使用错误。
validator 不读取原因、建议等验收标签，也不会替模型判断业务原因。
合法但错误的诊断仍由独立 oracle 拒绝。原 Qwen 模型运行、失败及报告见
[真实模型实验记录](../examples/model-results.md)；开发回归题、公开留出题
和工程 fixture 在报告中分别标明，不能混算模型表现。

原 Qwen3 4B 的 verified 开发回归为 2/2，公开留出为 7/8。前者是根据开发
错误选择的两个回归案例，后者也没有同版本 baseline 对照；这些结果说明
该配置下的实际表现，不能归因于训练或写成公平提示实验的提升。

每次实验记录模型 digest、代码和数据指纹、生成配置、工具 schema、
预算、种子、运行环境和原始 trace 哈希。统计按任务配对，重复 trial 的
bootstrap 以任务为单位，避免把同一个任务的重复运行当成独立样本。
未知 token 用量和未完成任务保留在结果中，不悄悄从分母删除。

## 从轨迹候选走到真正的模型训练

原导出器只接受开发集里真实模型完成且独立 oracle 全通过的轨迹。导出前
检查 trace SHA-256、配置、任务提示、相对路径及实际消息，并重新评分；
失败、fixture 和留出集不会导出。8 条成功候选经过自动技术复核，但仍保留
`human_review_required=true`，没有把自动审查写成人工已经审查。

实际训练实验使用固定 revision 的 `SmolLM2-135M-Instruct`，适应 CPU
资源。它学习一个受约束的多步工具策略：原始语言模型词表中的 9 个字母
token 分别表示 3 个真实工具动作和 6 类终止诊断。每次仍由 Transformer
计算语言头 logits；不是另写分类器或脚本替模型选工具。操作者绑定工具
参数，最终数值、引用和 JSON 由机械渲染器复制，因而这项评测明确叫
“受约束策略加渲染器”，不与原 Qwen 自由生成 JSON 的成功率混比。

训练前冻结 18 个开发训练服务、6 个开发验证服务和 8 个公开留出服务。
SFT 的 72 条动作监督来自 18 个开发案例的四步路径，明确标注
`synthetic-supervised`：开发标签提供教师诊断，工具提供实际观测。它们
不是冒充模型生成的成功轨迹；原 8 条长 Qwen 聊天记录没有硬塞给小模型。
监督损失是 9 个合法原始词表 token 上的条件交叉熵，梯度更新注意力层的
`q_proj` 与 `v_proj` LoRA 参数。

RL 从当前小模型采样多步 episode，实际执行工具。奖励考虑独立验收结果、
工具覆盖、重复调用和预算终止，不给未执行的工具虚构证据。使用
REINFORCE：每条 episode 的奖励减去同组其他 episode 的平均奖励作为
基线，按 advantage 加权动作 log probability，除以固定 episode 数。
进入 RL 前重建优化器，清除 SFT 动量；默认没有熵奖励，避免仅凭熵或旧
动量产生的权重变化宣称完成了奖励驱动训练。

Base、SFT 和 SFT+RL 使用同一组冻结的 6 个验证服务和 8 个公开留出服务，
用相同 greedy 解码与任务契约比较。保存每步动作概率、真实 observation、
奖励、损失和梯度范数，以及三个阶段的 adapter 文件及 SHA-256。重新加载
SFT 与 RL adapter 前故意扰动每个 LoRA tensor，要求保存的权重完全恢复，防止空操作加载器
通过表面上的哈希一致检查。完整命令、实际结果入口和方法边界见
[训练说明](training.md)；具体分数以实验 `report.md` 与 `summary.json`
为准，参数改变不自动意味着能力提升。

## 实际完成了哪些训练，结果怎样

固定的 CPU 实验实际更新了 **230,400 个 LoRA 参数**，运行 72 次 SFT
optimizer update，以及 8 次 RL group update，每组采样 4 条 episode。
72 条监督数据与 72 次更新是两个计数。8 个 RL 组中，5 组具有非零
advantage、奖励梯度及参数变化，3 组 advantage 为零。不能把 32 条
rollout 都说成有效梯度更新。

| 阶段 | 6 个开发验证任务的完整成功 | 8 个公开留出任务的完整成功 | 三类工具观测齐全 |
|---|---:|---:|---:|
| 未训练的 Base | 0/6 | 0/8 | 0/14 |
| SFT | 3/6 | 3/8 | 14/14 |
| SFT 后 REINFORCE | 2/6 | 3/8 | 14/14 |

这里的“完整成功”指受约束策略加机械渲染器通过独立 oracle 的全部检查。
SFT 学会了完整使用三类工具，但工具覆盖 14/14 并不等于诊断全部正确。
这次 RL 没有提高留出成功率，验证集还从 3/6 退化到 2/6；原始失败全部
保留，没有依据留出结果重调后替换报告。小样本、公开合成任务和受约束
动作空间决定了这些数字不能与 Qwen 4B 自由 JSON 结果混比。

训练的五项执行校验全部通过：SFT 参数改变、SFT 扰动后恢复、RL 参数
改变、真实奖励梯度活跃、RL 扰动后恢复。公开了 initial、sft、reinforce
三个 adapter、配置、权重哈希和逐步日志，详见
[实际训练报告](../examples/experiments/training-v3/report.md) 与
[机器可读结果](../examples/experiments/training-v3/summary.json)。

随后独立消费者在新输出目录加载已保存的 RL adapter，完成 14 条任务，
确认加载参数哈希正确、评测前后参数不变，并复现原来的动作、决策和
oracle 检查。**复现匹配为 14/14，业务完整成功仍是 5/14（验证 2/6、
留出 3/8）**。它证明权重可复用及结果可重复，也复现了原来的失败。
证据见 [消费者报告](../examples/experiments/adapter-consumer-v3/report.md) 与
[summary.json](../examples/experiments/adapter-consumer-v3/summary.json)。若只按
开发验证选择演示策略，保留 SFT（3/6）优于本轮 RL（2/6）；这是对已完成
结果的选择，不改冻结实验或根据公开留出再训练。

## 怎样在本地演示这条数据流

在两个仓库按 [复现说明](reproduce.md) 安装后，从 eval 根目录先运行：

```bash
byte-agent dataset --data runs/walkthrough-data
python -m byte_eval run --fixture --split dev --profiles verified --output runs/walkthrough-fixture
```

fixture 用于快速检查真实工具、journal、输出与 oracle 的接线；它不会调用
大模型，不能作为模型能力分数。真实 Qwen 诊断使用复现说明中的固定模型
来源、配置和独立目录；打开其中一条 `trace.json`，沿着模型消息、工具
参数、真实 observation、最终 JSON 和各项评分阅读，再找一条失败对照。

训练权重演示不需要重新训练。先用公开的
[固定模型下载器](../examples/download_training_model.py) 获取并校验七个
基础模型文件及 `download-manifest.json`，再运行
[adapter 消费者](../examples/evaluate_adapter.py)。命令如下：

```bash
python examples/download_training_model.py
python examples/download_training_model.py --verify-only
python examples/evaluate_adapter.py --model .deps/models/SmolLM2-135M-Instruct/12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --checkpoint examples/experiments/training-v3/checkpoints/reinforce \
  --dataset runs/walkthrough-data/services.json --output runs/walkthrough-adapter \
  --split all --reference examples/experiments/training-v3/reinforce-evaluation.json
```

先按 [训练说明](training.md) 安装 CPU 训练依赖，并设置其中给出的 frozen
archive `PYTHONPATH`，再执行消费者，才能绑定原训练的 26 个源码哈希。
两个仓库分别保存了 16 个平台与 10 个评测源码文件；它们来自历史训练
checkpoint。后来的 V4 metrics 引用修复、V5 提示澄清、V6 观测一致性
及 V7 实际引用绑定均有独立来源，见 [V4 元数据](../examples/multiagent-source-v4.json)、
[V5 元数据](../examples/multiagent-source-v5.json) 与
[V6 元数据](../examples/acceptance-source-v6.json)、
[V7 元数据](../examples/acceptance-source-v7.json)，不会改写原训练源码指纹。
新输出目录的 `summary.json` 将复现匹配、工具覆盖和业务成功
分列；每次使用新目录，保留执行证据。

## 怎样对应岗位 JD

| JD 方向 | 项目中实际做的内容 | 演示时可打开的证据 |
|---|---|---|
| Agent 架构与应用 | ReAct 研发诊断、四角色协作、上下文与执行预算 | 平台 runtime、角色 trace、独立 oracle |
| 工具与知识基建 | SQL 指标和变更工具、BM25/可选 Embedding、MCP、可信 Skill | 工具 schema、检索引用、SDK 集成测试 |
| Agentic Eval | 同模型提示对照、工具消融、业务契约、任务配对统计 | experiment 配置、失败检查、原始 trace |
| SFT 与 Agentic RL | 真实小 LM LoRA、隔离监督数据、执行工具奖励和 REINFORCE | 三阶段 adapter、训练日志、前后评测 |
| 可用性与扩展性 | durable journal、uncertain 恢复、租约/心跳/fencing、网络 worker | 崩溃恢复与旧 token 拒绝记录 |

例如面试中可以说明：先把“诊断得像不像”改成可独立验收的任务；再把模型
决策和工具执行分开；从失败中定位窗口、参数、格式和证据错误；最后用
训练日志验证权重确实更新，同时接受 RL 没有改善业务结果。HTTP worker
展示的是执行与恢复原型，跨主机和生产规模结论需要对应实测证据。

## 面试时怎样讲清楚

先演示一条真实任务，从模型动作、工具参数和 observation 讲到最终 JSON
及 oracle 检查，再展示一条失败，说明失败发生在格式、证据、工具还是
业务决策。接着解释为什么需要 service scope、执行恢复和 fencing。
最后打开训练 adapter、配置及日志，讲清监督数据如何生成，奖励来自什么，
为什么训练和评测服务分开，以及前后结果是否支持“提升”的结论。

这组项目提供的是可复现的 Agent 工程、评测和小模型训练经验。当前任务
数据是公开合成场景，CPU 小模型使用受约束动作空间；不能据此声称已改善
原 Qwen 4B、已经产生线上收益，或达到大型生产集群的 SLA。
