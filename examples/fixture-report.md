# 工程 fixture 验收

Scripted 预设轨迹只验证软件，不能用于模型能力或训练提升声明。

| 数据划分 | Profile | Trial | 完整验收成功 |
|---|---|---:|---:|
| dev | baseline | 24 | 24 |
| dev | grounded | 24 | 24 |
| dev | no-changes | 24 | 0 |
| holdout | baseline | 8 | 8 |
| holdout | grounded | 8 | 8 |
| holdout | no-changes | 8 | 0 |

两个完整工具组使用相同预设动作，不人为制造提示收益。no-changes 缺少契约规定的当前变更证据，主 success 会机械失败；不能把这个 0% 当作纯推理差距。

[dev 原始报告](experiments/release-fixture-dev/report.md) · [holdout 原始报告](experiments/release-fixture-holdout/report.md)。两套共记录 96 trial，complete=true。

新增 verified 工程处理在集成测试中覆盖全部 32 案例，测试只验证范围限制、引用、数值与修正预算。实际模型表现与全部失败记录见 [model-results.md](model-results.md)。

