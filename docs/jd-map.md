# Agent 实习岗位：评测与训练部分的证据

本页对应 ByteIntern JD 中的 Agentic Eval、SFT、Agentic RL 和工具规划。
平台架构、MCP、Skill、Multi-Agent 与执行可靠性见
[配套平台](https://github.com/chendi-Shi/byte-agent-platform)。学历、毕业时间
和个人独立掌握程度需要申请者另行证明。

| JD 内容 | 本项目实现 | 验证入口 | 解释范围 |
|---|---|---|---|
| 构建 Agentic Eval | 32 个独立合成服务、严格结构化决策与真实工具证据验收、失败归因 | [scoring.py](../src/byte_eval/scoring.py)、[设计说明](design.md) | 枚举诊断契约，不是任意开放式文本或生产因果验证 |
| 调整规划与工具使用 | 同工具／预算的 prompt 对照、取消变化工具的消融、观测驱动 verified 工程处理 | [experiment.py](../src/byte_eval/experiment.py)、[原 Qwen 实测](../examples/model-results.md) | verified 包含 scope 与校验，不是纯 prompt 收益；消融完整性差值不证明推理提升 |
| SFT 数据治理 | dev-only、真实非 fixture、完整成功、哈希与配置核验、独立复评分、消息去重 | [review.py](../src/byte_eval/training/review.py)、原实验的 `sft-candidates.jsonl` | 原 8 条候选仍需人工审查，没有进入小模型训练 |
| 实际 SFT 流程 | SmolLM2 135M 固定基础权重；72 条开发 synthetic-supervised 动作；q/v LoRA；真实条件 token 损失 | [policy.py](../src/byte_eval/training/policy.py)、[训练说明](training.md) | 受约束小模型策略，与 Qwen3 4B 训练或完整自由生成能力有明确区别 |
| Agentic RL | 当前 LM 采样多步动作，实际执行工具，独立验收奖励，leave-one-out REINFORCE | [environment.py](../src/byte_eval/training/environment.py)、[policy.py](../src/byte_eval/training/policy.py) | REINFORCE，不是 PPO／GRPO；单 CPU、小型公开合成环境 |
| 训练前后验收 | 18 train／6 dev validation／8 public holdout；统一 greedy；权重改变、哈希和扰动加载验证 | [V3 report](../examples/experiments/training-v3/report.md)、[summary](../examples/experiments/training-v3/summary.json) | 分数以实际实验为准；参数变化不等于能力提升，公开 holdout 不是隐藏生产基准 |

面试时能展示的关键链条是：任务定义 → 模型动作 → 实际工具 observation →
独立 oracle → 来源受控的数据 → 真实梯度和 adapter → 统一口径前后评测。
没有这条证据链的提升数字、人工审查、生产收益或规模经验不能写成已完成。
讲述顺序见 [面试说明](interview.md) 和 [中文项目讲解](project-walkthrough.zh-CN.md)。
