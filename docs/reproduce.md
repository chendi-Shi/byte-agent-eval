# 从空目录复现

以下命令定义工程检查和发布实验配置，不构成实验已完成或模型提升的声明。实际状态、分数及公开原始目录以 [模型实测记录](../examples/model-results.md) 为准。需要 Python 3.11+、Git；真实模型运行另需已运行的本地 Ollama 服务和可调用工具的模型。核心 Python 项目没有第三方运行依赖；下面安装平台的可选 MCP 依赖以验证官方 SDK 集成。

## 克隆与工程检查

两个仓库放在同一父目录：

```bash
git clone https://github.com/chendi-Shi/byte-agent-platform
git clone https://github.com/chendi-Shi/byte-agent-eval
cd byte-agent-platform
python -m pip install -e ".[mcp]"
python -m unittest discover -s tests -v
cd ../byte-agent-eval
python -m pip install -e .
python -m unittest discover -s tests -v
```

记录两个仓库的 `git rev-parse HEAD`，正式实验期间冻结源码、数据、任务与提示。若不安装包，可用 `PYTHONPATH=src`；PowerShell 使用 `$env:PYTHONPATH='src'`。下面命令均在 `byte-agent-eval` 根目录执行，默认平台路径为 `../byte-agent-platform`，可用 `--platform` 改为对应位置。

先运行全部 24 dev 和 8 holdout 的软件 fixture：

```bash
python -m byte_eval run --fixture --split dev --profiles baseline grounded no-changes --output runs/v2-fixture-dev
python -m byte_eval report --output runs/v2-fixture-dev --include-fixtures
python -m byte_eval run --fixture --split holdout --profiles baseline grounded no-changes --output runs/v2-fixture-holdout
python -m byte_eval report --output runs/v2-fixture-holdout --include-fixtures
python -m byte_eval export-sft --output runs/v2-fixture-dev --destination runs/v2-fixture-candidates.jsonl
```

最后一条导出应为 0。baseline/grounded fixture 使用同一脚本，不能用其结果宣称提示收益；no-changes 缺失当前变更工具，完整证据检查会失败。这些是工程检查，默认模型报告排除 fixture。

默认 profiles 始终是 `baseline grounded no-changes`；`verified` 必须显式选择。需要检查当前版本的 scoped tools 和 verifier 时，可以另开目录运行 `--fixture --profiles verified`，分别覆盖 dev 与 holdout。两组 fixture 都不进入模型统计或训练候选。

## 模型与运行环境

正式命令使用本地 `qwen3:4b-instruct`。先用 `ollama list` 确认该确切名称和本机模型来源，再用 `ollama show qwen3:4b-instruct --modelfile` 保存其模板配置。这个名称是本地模板版本，不是已训练权重的声明；不能仅根据同名模型假设权重和模板相同。若已安装原始 `qwen3:4b`，可用平台的兼容工具创建另一个标签：

```bash
python -m byte_agent prepare-model --model qwen3:4b --target qwen3:4b-instruct
```

此命令针对旧 Qwen Go 模板的工具 schema 序列化进行兼容修复，保留原权重，不是 SFT/RL。它会创建目标标签；复用已有实验时应保持原标签及 digest，不要覆盖后继续写同一个目录。若原始模型未安装，先按模型提供者和 Ollama 的正式说明准备。替换模型名必须使用新实验目录，并记录替换原因。

记录 CPU/GPU、可用内存、Ollama 版本、模型 digest、量化、上下文与输出上限。套件通过提供者记录可获取的模型版本和 generation 配置，但硬件资源及服务并发负载仍需另存。模型服务已启动后才运行评测；评测不会自动下载模型或启动训练。

这组正式配置采用 `model-context=3072`、每次模型输出上限 `384`、单请求 timeout `300` 秒、每个任务 runtime token 预算 `48000`、最多 `8` 模型步骤和 `16` 工具调用。每 trial 的实际总 token 以提供者返回的用量为准；48000 是运行停止预算，不是模型上下文长度。各模型/profile 使用相同参数和基础 seed 42。

## 8 个 dev，三种 profile

旧版发布实验在两套源码均冻结时运行。精确 checkpoint 如下：

| 项目 | 冻结 commit |
|---|---|
| byte-agent-platform | `df796059446bf87ae630f144b15dc90ccba2cfe2` |
| byte-agent-eval | `28264e9364fe5d395eb28eb1e7dc558afbc79fca` |

从当前克隆创建独立的 detached worktree，保留当前开发版本，安装匹配的冻结代码：

```bash
git -C ../byte-agent-platform worktree add --detach ../byte-agent-platform-v2-checkpoint df796059446bf87ae630f144b15dc90ccba2cfe2
git -C . worktree add --detach ../byte-agent-eval-v2-checkpoint 28264e9364fe5d395eb28eb1e7dc558afbc79fca
cd ../byte-agent-eval-v2-checkpoint
python -m pip install -e ../byte-agent-platform-v2-checkpoint
python -m pip install -e .
```

八个 dev 服务覆盖发布、依赖、容量、健康、缺失指标、冲突证据和检索注入。它们是完整 24 dev 的预先列出的子集，不能标成全 24 dev 实验。在上述冻结 eval 目录执行以下命令，一次重复计划 24 条 trial：

```bash
python -m byte_eval run --platform ../byte-agent-platform-v2-checkpoint --model qwen3:4b-instruct --split dev --task-ids growth-feed creator-upload live-session discovery-nearby social-follow search-reindex ads-attribution growth-invite --profiles baseline grounded no-changes --trials 1 --seed 42 --model-context 3072 --model-output 384 --timeout 300 --max-steps 8 --max-calls 16 --max-tokens 48000 --output runs/v2-formal-dev-8
python -m byte_eval report --output runs/v2-formal-dev-8
python -m byte_eval export-sft --output runs/v2-formal-dev-8 --destination runs/v2-formal-dev-8/sft-candidates.jsonl
```

baseline/grounded 是同工具、同预算的提示对比；no-changes 是移除因果工具的能力消融。主成功要求完整证据，因此工具消融的完整成功率会机械受限；同时查看次级决策 accuracy 和 cause/recommendation 检查，不以完整性差值宣称推理提升。

增加 `--trials` 需要预先确定新计划并换目录，例如 `runs/v2-formal-dev-8-t3`。同一任务的重复不增加独立任务数；trial 的种子为 `42 + trial index`，各 profile 保持一致。开发探针可以使用一个 `--task-ids` 和独立输出目录，不能混入正式实验或跨配置配对。

用公开 `experiment.json` 核对模型 digest/模板指纹、生成配置、任务、两套源码指纹与预算，再复跑。相同模型名称不能替代 digest 校验。运行机器、Ollama 版本或模板不同可能影响结果；保留新输出，不能覆盖发布的原始实验或声称新的 config hash 与原记录相同。

## 新版 verified：两个 dev 回归任务

新版 verified 实验使用下面两套冻结源码。与 [模型实测记录](../examples/model-results.md) 的源码指纹核对后，创建独立 worktree 并安装；旧平台 checkpoint 没有所需 validator 接口：

| 项目 | verified 冻结 commit |
|---|---|
| byte-agent-platform | `8ffe6eeece82305b85094337aef145c316b11526` |
| byte-agent-eval | `aff57b9d6496a4f3e228fc9e4bb2d0139101e357` |

```bash
cd ../byte-agent-eval
git -C ../byte-agent-platform worktree add --detach ../byte-agent-platform-verified-checkpoint 8ffe6eeece82305b85094337aef145c316b11526
git -C . worktree add --detach ../byte-agent-eval-verified-checkpoint aff57b9d6496a4f3e228fc9e4bb2d0139101e357
cd ../byte-agent-eval-verified-checkpoint
python -m pip install -e ../byte-agent-platform-verified-checkpoint
python -m pip install -e .
```

`verified` 是 service enum scope、确定性的 JSON/观测/引用校验和预算内修正处理，kind 为 `tool_scope_and_output_validation`。它不读取 gold 标签、不替模型选择原因或建议。两个 dev 回归题 `creator-upload`、`live-session` 由开发错误选出；它们不是随机泛化测试。以下一次重复计划 2 条 trial：

```bash
python -m byte_eval run --platform ../byte-agent-platform-verified-checkpoint --model qwen3:4b-instruct --split dev --task-ids creator-upload live-session --profiles verified --trials 1 --seed 42 --model-context 3072 --model-output 384 --timeout 300 --max-steps 8 --max-calls 16 --max-tokens 48000 --output runs/v3-verified-dev-2
python -m byte_eval report --output runs/v3-verified-dev-2
python -m byte_eval export-sft --output runs/v3-verified-dev-2 --destination runs/v3-verified-dev-2/sft-candidates.jsonl
```

它增加了执行前的工具 service 限制与最终回答校验，因此不是纯提示对比。修正消耗原有预算；错误服务历史、被阻断的非法调用和工具错误仍保留失败。此组不与旧配置计算配对 delta，也不能将成功率变化归因于训练。

## 新版 verified：8 个 holdout

holdout 使用八个与 dev 不同的服务，包含缺失手册等案例。提示、scope 和 validator 在查看 holdout 模型结果前冻结。以下命令一次重复计划 8 条 trial，仅评 verified；它没有同版本 baseline 对照，不能产生 holdout 的纯提示提升结论：

```bash
python -m byte_eval run --platform ../byte-agent-platform-verified-checkpoint --model qwen3:4b-instruct --split holdout --task-ids holdout-comment holdout-local-order holdout-live-caption holdout-creator-stats holdout-recommend-cache holdout-market-tax holdout-direct-call holdout-content-export --profiles verified --trials 1 --seed 42 --model-context 3072 --model-output 384 --timeout 300 --max-steps 8 --max-calls 16 --max-tokens 48000 --output runs/v3-verified-holdout-8
python -m byte_eval report --output runs/v3-verified-holdout-8
```

若后续需要 holdout 的公平提示对比，须预先固定同版本源码、相同八个任务和上述参数，在新目录运行 `--profiles baseline grounded`。公开 holdout 不是隐藏生产测试集；不得把它用于候选训练、查看结果后逐案调整验证规则，或混入 dev 的 SFT 导出。

## 核对结果与恢复

每套实验保留 `experiment.json`、`results.json`、`summary.json`、`report.md`，以及每 trial 的 SQLite journal 和 `trace.json`。计划与记录条数应对应；旧版 dev 子集为 24，verified dev 为 2，verified holdout 为 8，默认三组的完整 dev fixture 为 72、holdout fixture 为 24。条数是实验计划，不是结果已完成的保证。源码、数据、模型或参数变化都会导致已有目录的配置校验拒绝复用，应保留旧目录并换新目录。

报告应读取主 success、次级决策 accuracy、全部检查失败、JSON 解析失败、已知与未知 token 用量、wall time、缺失 trial 和配对缺口。`complete=false` 或 `interrupted.json` 表示实验未完成，不能仅从已返回的成功条目推断整个实验效果。`uncertain` 会立即停止后续任务，不自动重试响应丢失的请求；调查提供者后另开实验目录，并保留失败记录。

同一目录只允许一个套件进程串行写入。已完成且配置一致的 trial 可被串行续跑复用；运行中避免编辑源码、替换模型或同时生成同目录报告。原样复制整个输出目录后，相对 trace 路径仍可用于导出；改动原始 trace 将使 SHA256 校验失败。

SFT 输出只是成功真实 dev 轨迹的候选 messages，包含 `human_review_required=true`，应人工审阅并转换训练格式。候选数量可能为 0；不能补入 fixture、holdout 或失败轨迹凑数。service scope、模板兼容修复和输出校验也没有改变模型权重，不能把这些工程处理或候选导出表述成已经完成 SFT/RL 训练。
