# Byte Agent Eval

面向 Agent 规划、工具使用与最终结果的独立评测项目，配套 [Byte Agent Platform](https://github.com/chendi-Shi/byte-agent-platform)。覆盖 32 个合成业务服务、严格证据验收、公平提示对照、工具消融、统计报告、可审计的 SFT 候选导出，以及独立的 CPU 小语言模型 LoRA SFT／REINFORCE 工具策略训练。

原评测核心通过 35 项测试；新增训练模块的 9 项真实工具／隔离／来源检查和 7 项真实 PyTorch 梯度／加载检查也已通过。真实 Qwen3 4B 验证模式在开发回归中通过 2/2，在完整留出集中通过 7/8（87.5%）；两个开发实验合计导出 8 条待人工审查的 SFT 候选。原 Qwen 配置、分数、统计范围和全部失败轨迹见 [examples/model-results.md](examples/model-results.md)。开发回归有选择偏差，留出样本仅 8 个。Scripted 结果只验证软件，默认从模型统计与训练候选排除。

新增 SmolLM2-135M-Instruct 训练更新的是小模型注意力 LoRA，使用受约束动作与机械答案渲染；完整 SFT／REINFORCE 已运行，五项实际参数／梯度／加载验收全部通过。下表完整记录三阶段同口径分数，不能与原 Qwen3 4B 自由生成任务直接比较。流程见 [训练说明](docs/training.md)，[V3 全部证据](examples/v3-results.md) 和 [中文项目讲解](docs/project-walkthrough.zh-CN.md)说明干了什么、怎么做。

<!-- V3 actual results: begin -->

## V3 实际训练结果

候选 commit 的 GitHub CI：平台在 Windows、Ubuntu 各 140 项通过且无跳过；评测核心在两系统各运行 51 项，其中 44 项通过、7 项因训练依赖跳过。独立 training-contracts job 实际通过 9 项训练环境测试和 7 项策略测试；后者逐个覆盖核心跳过项，合并为 51 个不同测试，重复测试不累加。这些是候选 CI 结果；最终 main CI 另行核验，本机失败记录保留。

实际训练模型为 `HuggingFaceTB/SmolLM2-135M-Instruct`，revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`；LoRA rank 4，可训练参数 230,400。SFT 72 步（batch 4，lr 0.001），REINFORCE 8 步（group 4，lr 0.0001，entropy 0）。

SFT loss 首步／末步／均值为 `3.44924/0.0019207/0.815568`；RL loss 为 `0.0610409/0/-0.186929`。5/8 个 RL 步骤具有非零 reward advantage、梯度并实际改变参数。SFT 与 RL 参数变化、两阶段扰动后精确加载和 reward 梯度五项检查全部通过。


| 阶段 | 分组 | 完整契约通过（含渲染器） | 决策正确 | 三工具齐全 | 平均 reward |
|---|---|---:|---:|---:|---:|
| base | 开发验证 | 0/6 | 0/6 | 0/6 | -0.633 |
| base | 公开留出 | 0/8 | 0/8 | 0/8 | -0.450 |
| sft | 开发验证 | 3/6 | 3/6 | 6/6 | 0.800 |
| sft | 公开留出 | 3/8 | 3/8 | 8/8 | 0.675 |
| reinforce | 开发验证 | 2/6 | 2/6 | 6/6 | 0.633 |
| reinforce | 公开留出 | 3/8 | 3/8 | 8/8 | 0.675 |


这项评测使用原始词表中九个动作 token、操作者绑定的工具参数及机械数值／引用／JSON 渲染器。18 个服务用于训练，6 个用于开发验证，8 个公开留出只用于评测；72 条监督记录标记为 synthetic-supervised。它衡量 135M 受约束工具策略加渲染器，不能与自由生成答案的 Qwen3 4B 分数直接相减。表中零提升或下降也保留；小样本单次运行不证明生产泛化。

| checkpoint | 参数 SHA256 | adapter 文件 SHA256 | 权重与说明 |
|---|---|---|---|
| initial | `5ccfe6b7912f75a631897f281127d6029c0f736cb022434b27c454e62b222c72` | `5a50515d4764f29b65e6baf0ae55d4f3b6856b9d9b523953878f3febe42274ec` | [adapter](examples/experiments/training-v3/checkpoints/initial/adapter_model.safetensors) · [元数据](examples/experiments/training-v3/checkpoints/initial/weights.json) |
| sft | `f744026542e6676fac01dae20087246bc1b78530386ead9a5b37c8858052c4c9` | `2d4fd5e972e04ca7b1c0279bd0877095985fd0b208635665eda75cb4c7c6f2fd` | [adapter](examples/experiments/training-v3/checkpoints/sft/adapter_model.safetensors) · [元数据](examples/experiments/training-v3/checkpoints/sft/weights.json) |
| reinforce | `a4fd3641e75d2f4b4188289794431be654ec37e4cd2d13e57ae83fb7c84ac6e2` | `80e0d44a3be4b7ada64024ba8b57c11a3acb09a4159894a50cf0d132f63927b0` | [adapter](examples/experiments/training-v3/checkpoints/reinforce/adapter_model.safetensors) · [元数据](examples/experiments/training-v3/checkpoints/reinforce/weights.json) |

公开 reinforce adapter 随后在全新 consumer 进程中重新加载：文件／元数据 SHA256 与加载后参数 hash 均匹配，optimizer_steps=0，评测前后参数 hash 不变。14 个任务的动作、决策和全部 oracle checks 与原结果一致，包括原失败；这是复现一致性，不是 14/14 业务通过。耗时和浮点概率没有宣称逐位一致。[consumer summary](examples/experiments/adapter-consumer-v3/summary.json) · [14 条 consumer 评测及 trace](examples/experiments/adapter-consumer-v3/reinforce-evaluation.json)。

26 个冻结训练源码 SHA256 已绑定并核对不可变 Git commit 与实际 blob：[源码绑定](examples/v3-source-binding.json)。


配置 hash：`5023bce6122e40a42e25679a501003c69b07b19ff533e7d39f47084cc038aecb`。

[summary](examples/experiments/training-v3/summary.json) · [manifest](examples/experiments/training-v3/manifest.json) · [实际训练日志](examples/experiments/training-v3/training-log.json) · [全部训练报告](examples/experiments/training-v3/report.md)。

<!-- V3 actual results: end -->

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

正式模型运行不读取验收标签作为输入；model 只接收 task prompt、工具 schema 和工具返回的合成观测。下例的 `qwen3:4b-instruct` 是本地模板标签：首次使用先按 [模型准备](docs/reproduce.md#模型与运行环境) 下载 `qwen3:4b`，再执行 `python -m byte_agent prepare-model --model qwen3:4b --target qwen3:4b-instruct`；不要直接下载这个自定义标签。

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

导出为 Ollama-chat messages，包括模型动作和工具观测；带来源、配置指纹与 `human_review_required=true`。导出本身是候选数据准备，不能直接宣称 SFT/RL 提升。8 条已有候选经自动技术复评分，仍保留人工审查要求；这些长轨迹没有直接混入下面的小模型训练。

候选仍需人工审查；数量为 0 时保留真实结果，不能用 fixture、holdout 或失败轨迹补齐。模板兼容修复与验证反馈也不属于训练。

## CPU 小模型 SFT 与 Agentic RL

固定官方 SmolLM2-135M-Instruct revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`。冻结 18 个开发训练服务、6 个开发验证服务和 8 个公开留出服务；72 条动作监督明确标注 `synthetic-supervised`，使用开发教师标签与实际工具观测，排除验证／留出服务和 fixture。

模型从原始词表的 9 个单 token 动作中选择三种工具调用或六类终止诊断。SFT 条件交叉熵实际反传到 `q_proj`／`v_proj` LoRA rank 4。REINFORCE 采样真实多步工具 episode，使用独立验收与工具覆盖／重复／预算奖励、同组其他 episode 的奖励基线和固定 episode 数归一化。RL 前重建优化器清除 SFT 动量；默认熵项为零。每阶段保存 adapter 与 SHA-256，加载前先扰动所有 LoRA tensor，再要求完全恢复，避免空加载器伪通过。

Base／SFT／SFT+RL 在同一组 6+8 服务上以相同 greedy 解码与渲染器评测。操作者固定工具参数，渲染器复制实际指标和引用、输出严格 schema，因此这项结果是“受约束策略加渲染器”，不能与自由生成 JSON 的 Qwen 成功率直接对比。源码不会在隐式模型下载失败后退回脚本或随机模型；真实失败、零提升和负提升均保留。

公开 adapter 可通过 [消费者示例](examples/evaluate_adapter.py) 单独加载和评测，无须重新训练。消费者的 14 条结果匹配同时包括原有成功与失败，不能写成 14 条业务任务全通过；业务成功率另看每个 split 的 `full_contract_successes_with_renderer`。

安装和执行命令见 [训练说明](docs/training.md)；[固定依赖](requirements-training-lock.txt) 记录实际环境，CPU training CI 用极小随机 Llama 验证真实 autograd／保存／恢复，不下载 135M 权重，不冒充模型性能实验。

## 来源与范围

参考 [AgentBench](https://github.com/THUDM/AgentBench)、[AgentDojo](https://github.com/ethz-spylab/agentdojo) 的独立验收与攻击/任务效果并行评估思路；代码与合成数据独立实现，没有运行或宣称这些官方 benchmark 分数。[设计说明](docs/design.md) 记录取舍。

公开 holdout 用于验证服务隔离和工程复现，不是隐藏的生产泛化基准。小模型训练在 CPU 上进行；没有生产数据、生产规模测试或无条件安全保证。应按仓库记录的实测结果描述项目。岗位对应与讲述入口见 [JD 对齐](docs/jd-map.md) 和 [面试讲述](docs/interview.md)。
