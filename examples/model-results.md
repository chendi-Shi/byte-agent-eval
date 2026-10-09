# 模型实测与工程验收

本页由原始 experiment、summary 和 results 生成；未记录完成标志、缺失 trial 或记录不一致的实验均明确标为未完成/待核对。
complete 表示实验记录齐全，不能替代每条任务的成功验收。fixture 只验证软件，开发探针不混入正式实验。

fixture 的 unknown_usage 是 Scripted 未提供 token 字段时产生的运行时记账，不表示实际模型请求；fixture 的 token 与用量统计不用于模型成本估算。

| 实验 | Profile / 处理 | 计划 | 已记录 | 套件完成状态 | Full success | Decision accuracy（次） | 已知 tokens | 未知用量 trial / request | Wall 总秒 / 中位秒 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| 旧版 8 dev × 3 profiles | baseline / prompt_baseline | 8 | 8 | 未完成 | 2/8 (25.0%) | 2/8 (25.0%) | 20468 | 0 / 0 | 1478.55 / 189.23 |
| 旧版 8 dev × 3 profiles | grounded / prompt_treatment | 8 | 8 | 未完成 | 4/8 (50.0%) | 4/8 (50.0%) | 25801 | 0 / 0 | 2009.49 / 252.48 |
| 旧版 8 dev × 3 profiles | no-changes / causal_tool_ablation | 8 | 8 | 未完成 | 0/8 (0.0%) | 1/8 (12.5%) | 21634 | 1 / 1 | 1462.41 / 179.46 |
| verified 两个 dev 回归题 | verified / tool_scope_and_output_validation | 2 | 2 | 完整 | 2/2 (100.0%) | 2/2 (100.0%) | 7223 | 0 / 0 | 494.70 / 247.35 |
| verified 八个 holdout | verified / tool_scope_and_output_validation | 8 | 8 | 完整 | 7/8 (87.5%) | 7/8 (87.5%) | 31420 | 0 / 0 | 2032.10 / 230.38 |
| 0.6B 开发探针 | grounded / prompt_treatment | 1 | 1 | 完整 | 0/1 (0.0%) | 0/1 (0.0%) | 856 | 0 / 0 | 24.11 / 24.11 |
| 4B 开发探针 | grounded / prompt_treatment | 1 | 1 | 完整 | 1/1 (100.0%) | 1/1 (100.0%) | 3394 | 0 / 0 | 311.66 / 311.66 |
| 24 dev 工程 fixture | baseline / prompt_baseline | 24 | 24 | 完整 | 24/24 (100.0%) | 24/24 (100.0%) | 0 | 24 / 48 | 3.74 / 0.16 |
| 24 dev 工程 fixture | grounded / prompt_treatment | 24 | 24 | 完整 | 24/24 (100.0%) | 24/24 (100.0%) | 0 | 24 / 48 | 3.62 / 0.16 |
| 24 dev 工程 fixture | no-changes / causal_tool_ablation | 24 | 24 | 完整 | 0/24 (0.0%) | 7/24 (29.2%) | 0 | 24 / 48 | 3.08 / 0.12 |
| 8 holdout 工程 fixture | baseline / prompt_baseline | 8 | 8 | 完整 | 8/8 (100.0%) | 8/8 (100.0%) | 0 | 8 / 16 | 1.16 / 0.14 |
| 8 holdout 工程 fixture | grounded / prompt_treatment | 8 | 8 | 完整 | 8/8 (100.0%) | 8/8 (100.0%) | 0 | 8 / 16 | 1.19 / 0.14 |
| 8 holdout 工程 fixture | no-changes / causal_tool_ablation | 8 | 8 | 完整 | 0/8 (0.0%) | 3/8 (37.5%) | 0 | 8 / 16 | 0.99 / 0.12 |

统计分母为已记录 trial，必须同时阅读计划/完成列；不把未执行任务算作成功，也不隐藏其缺口。不同源码/配置的 trial 不进行配对。

## 旧版 8 dev × 3 profiles (`release-dev`)

原始材料：[experiment.json](experiments/release-dev/experiment.json)、[results.json](experiments/release-dev/results.json)、[summary.json](experiments/release-dev/summary.json)、[report.md](experiments/release-dev/report.md)。

计划 24 条；记录 24 条；summary.complete=False；复核 complete=False。

中断记录：`{"reason": "provider_uncertain", "task_id": "growth-invite", "profile": "no-changes", "recorded_trials": 24, "planned_trials": 24, "at": "2026-10-09T03:51:25.508393+00:00"}`。各组的实际终态见下方逐条 trace。

模型：`qwen3:4b-instruct`；digest：`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
量化：`Q4_K_M`；Ollama：`0.34.4`。

冻结平台 SHA：`df796059446bf87ae630f144b15dc90ccba2cfe2`；eval SHA：`28264e9364fe5d395eb28eb1e7dc558afbc79fca`。
实验 config_hash：`f95ca782d785eb9380c6ee32b84e8216d059100e68259f7fc50a3563851fbfe2`。

```json
{
  "generation": {
    "context": 3072,
    "output_tokens": 384,
    "timeout": 300.0,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 48000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**baseline**：首个失败 `{"numeric_answer": 3, "structured_answer": 1, "uncertainty_answer": 2}`；全部失败 checks `{"cause_answer": 3, "citation_ids": 1, "current_change_evidence": 1, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "numeric_answer": 4, "recommendation_answer": 3, "required_tools": 1, "runbook_evidence": 1, "service_answer": 1, "service_scoped_calls": 1, "status_answer": 1, "structured_answer": 1, "uncertainty_answer": 5}`。
JSON 解析失败 1 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

**grounded**：首个失败 `{"numeric_answer": 2, "structured_answer": 2}`；全部失败 checks `{"cause_answer": 2, "citation_ids": 2, "current_change_evidence": 2, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "numeric_answer": 4, "recommendation_answer": 2, "required_tools": 1, "runbook_evidence": 2, "service_answer": 2, "service_scoped_calls": 1, "status_answer": 2, "structured_answer": 2, "uncertainty_answer": 2}`。
JSON 解析失败 2 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

**no-changes**：首个失败 `{"cause_answer": 2, "completed": 1, "current_change_evidence": 1, "numeric_answer": 2, "structured_answer": 1, "uncertainty_answer": 1}`；全部失败 checks `{"cause_answer": 5, "citation_ids": 2, "completed": 1, "current_change_evidence": 8, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "numeric_answer": 4, "recommendation_answer": 5, "required_tools": 8, "runbook_evidence": 2, "service_answer": 2, "service_scoped_calls": 1, "status_answer": 2, "structured_answer": 2, "uncertainty_answer": 4}`。
JSON 解析失败 2 条；未知 provider 用量 1 个 trial / 1 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

SFT 候选：[sft-candidates.jsonl](experiments/release-dev/sft-candidates.jsonl)，6 条，其中 6 条带 human_review_required=true。候选导出不是训练，仍须人工审核。

每条原始 trace：

- [growth-feed/0/baseline](experiments/release-dev/traces/growth-feed/0/baseline/trace.json)；status=completed；full success=True
- [growth-feed/0/grounded](experiments/release-dev/traces/growth-feed/0/grounded/trace.json)；status=completed；full success=True
- [growth-feed/0/no-changes](experiments/release-dev/traces/growth-feed/0/no-changes/trace.json)；status=completed；full success=False
- [creator-upload/0/baseline](experiments/release-dev/traces/creator-upload/0/baseline/trace.json)；status=completed；full success=False
- [creator-upload/0/grounded](experiments/release-dev/traces/creator-upload/0/grounded/trace.json)；status=completed；full success=False
- [creator-upload/0/no-changes](experiments/release-dev/traces/creator-upload/0/no-changes/trace.json)；status=completed；full success=False
- [live-session/0/baseline](experiments/release-dev/traces/live-session/0/baseline/trace.json)；status=completed；full success=False
- [live-session/0/grounded](experiments/release-dev/traces/live-session/0/grounded/trace.json)；status=completed；full success=False
- [live-session/0/no-changes](experiments/release-dev/traces/live-session/0/no-changes/trace.json)；status=completed；full success=False
- [discovery-nearby/0/baseline](experiments/release-dev/traces/discovery-nearby/0/baseline/trace.json)；status=completed；full success=False
- [discovery-nearby/0/grounded](experiments/release-dev/traces/discovery-nearby/0/grounded/trace.json)；status=completed；full success=True
- [discovery-nearby/0/no-changes](experiments/release-dev/traces/discovery-nearby/0/no-changes/trace.json)；status=completed；full success=False
- [social-follow/0/baseline](experiments/release-dev/traces/social-follow/0/baseline/trace.json)；status=completed；full success=False
- [social-follow/0/grounded](experiments/release-dev/traces/social-follow/0/grounded/trace.json)；status=completed；full success=False
- [social-follow/0/no-changes](experiments/release-dev/traces/social-follow/0/no-changes/trace.json)；status=completed；full success=False
- [search-reindex/0/baseline](experiments/release-dev/traces/search-reindex/0/baseline/trace.json)；status=completed；full success=True
- [search-reindex/0/grounded](experiments/release-dev/traces/search-reindex/0/grounded/trace.json)；status=completed；full success=True
- [search-reindex/0/no-changes](experiments/release-dev/traces/search-reindex/0/no-changes/trace.json)；status=completed；full success=False
- [ads-attribution/0/baseline](experiments/release-dev/traces/ads-attribution/0/baseline/trace.json)；status=completed；full success=False
- [ads-attribution/0/grounded](experiments/release-dev/traces/ads-attribution/0/grounded/trace.json)；status=completed；full success=True
- [ads-attribution/0/no-changes](experiments/release-dev/traces/ads-attribution/0/no-changes/trace.json)；status=completed；full success=False
- [growth-invite/0/baseline](experiments/release-dev/traces/growth-invite/0/baseline/trace.json)；status=completed；full success=False
- [growth-invite/0/grounded](experiments/release-dev/traces/growth-invite/0/grounded/trace.json)；status=completed；full success=False
- [growth-invite/0/no-changes](experiments/release-dev/traces/growth-invite/0/no-changes/trace.json)；status=uncertain；full success=False

## verified 两个 dev 回归题 (`release-verified-dev`)

原始材料：[experiment.json](experiments/release-verified-dev/experiment.json)、[results.json](experiments/release-verified-dev/results.json)、[summary.json](experiments/release-verified-dev/summary.json)、[report.md](experiments/release-verified-dev/report.md)。

计划 2 条；记录 2 条；summary.complete=True；复核 complete=True。

模型：`qwen3:4b-instruct`；digest：`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
量化：`Q4_K_M`；Ollama：`0.34.4`。

冻结平台 SHA：`8ffe6eeece82305b85094337aef145c316b11526`；eval SHA：`aff57b9d6496a4f3e228fc9e4bb2d0139101e357`。
实验 config_hash：`2ee0dfb5f91126dfaa4e40f105ddb876950202008009ba9ec79744041a85ab05`。

```json
{
  "generation": {
    "context": 3072,
    "output_tokens": 384,
    "timeout": 300.0,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 48000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**verified**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 2 条。

SFT 候选：[sft-candidates.jsonl](experiments/release-verified-dev/sft-candidates.jsonl)，2 条，其中 2 条带 human_review_required=true。候选导出不是训练，仍须人工审核。

每条原始 trace：

- [creator-upload/0/verified](experiments/release-verified-dev/traces/creator-upload/0/verified/trace.json)；status=completed；full success=True
- [live-session/0/verified](experiments/release-verified-dev/traces/live-session/0/verified/trace.json)；status=completed；full success=True

## verified 八个 holdout (`release-holdout`)

原始材料：[experiment.json](experiments/release-holdout/experiment.json)、[results.json](experiments/release-holdout/results.json)、[summary.json](experiments/release-holdout/summary.json)、[report.md](experiments/release-holdout/report.md)。

计划 8 条；记录 8 条；summary.complete=True；复核 complete=True。

模型：`qwen3:4b-instruct`；digest：`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
量化：`Q4_K_M`；Ollama：`0.34.4`。

冻结平台 SHA：`8ffe6eeece82305b85094337aef145c316b11526`；eval SHA：`aff57b9d6496a4f3e228fc9e4bb2d0139101e357`。
实验 config_hash：`9d0a9fe53ac3ae60ecf495fd19e633fcd14f036969ed2c8772befff812a77772`。

```json
{
  "generation": {
    "context": 3072,
    "output_tokens": 384,
    "timeout": 300.0,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 48000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**verified**：首个失败 `{"status_answer": 1}`；全部失败 checks `{"cause_answer": 1, "recommendation_answer": 1, "status_answer": 1, "uncertainty_answer": 1}`。
JSON 解析失败 0 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

每条原始 trace：

- [holdout-comment/0/verified](experiments/release-holdout/traces/holdout-comment/0/verified/trace.json)；status=completed；full success=True
- [holdout-local-order/0/verified](experiments/release-holdout/traces/holdout-local-order/0/verified/trace.json)；status=completed；full success=True
- [holdout-live-caption/0/verified](experiments/release-holdout/traces/holdout-live-caption/0/verified/trace.json)；status=completed；full success=True
- [holdout-creator-stats/0/verified](experiments/release-holdout/traces/holdout-creator-stats/0/verified/trace.json)；status=completed；full success=True
- [holdout-recommend-cache/0/verified](experiments/release-holdout/traces/holdout-recommend-cache/0/verified/trace.json)；status=completed；full success=True
- [holdout-market-tax/0/verified](experiments/release-holdout/traces/holdout-market-tax/0/verified/trace.json)；status=completed；full success=False
- [holdout-direct-call/0/verified](experiments/release-holdout/traces/holdout-direct-call/0/verified/trace.json)；status=completed；full success=True
- [holdout-content-export/0/verified](experiments/release-holdout/traces/holdout-content-export/0/verified/trace.json)；status=completed；full success=True

## 0.6B 开发探针 (`probe-v2-06`)

原始材料：[experiment.json](experiments/probe-v2-06/experiment.json)、[results.json](experiments/probe-v2-06/results.json)、[summary.json](experiments/probe-v2-06/summary.json)、[report.md](experiments/probe-v2-06/report.md)。

计划 1 条；记录 1 条；summary.complete=True；复核 complete=True。

模型：`qwen3:0.6b-byte`；digest：`353d7af3742f55d7f641f44dc3f6723503d1f86bd6db3eff527497e1c0b6d997`。
量化：`Q4_K_M`；Ollama：`0.34.4`。

冻结平台 SHA：`df796059446bf87ae630f144b15dc90ccba2cfe2`；eval SHA：`28264e9364fe5d395eb28eb1e7dc558afbc79fca`。
实验 config_hash：`f0d3e28498f1cd1b95764f85f424207acf6da995ced1137c7543029595a9a4fb`。

```json
{
  "generation": {
    "context": 4096,
    "output_tokens": 512,
    "timeout": 180.0,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 24000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**grounded**：首个失败 `{"structured_answer": 1}`；全部失败 checks `{"cause_answer": 1, "citation_ids": 1, "current_change_evidence": 1, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "numeric_answer": 1, "recommendation_answer": 1, "required_tools": 1, "runbook_evidence": 1, "service_answer": 1, "status_answer": 1, "structured_answer": 1, "uncertainty_answer": 1}`。
JSON 解析失败 1 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 1 条。

每条原始 trace：

- [growth-feed/0/grounded](experiments/probe-v2-06/traces/growth-feed/0/grounded/trace.json)；status=completed；full success=False

## 4B 开发探针 (`probe-v2-4b`)

原始材料：[experiment.json](experiments/probe-v2-4b/experiment.json)、[results.json](experiments/probe-v2-4b/results.json)、[summary.json](experiments/probe-v2-4b/summary.json)、[report.md](experiments/probe-v2-4b/report.md)。

计划 1 条；记录 1 条；summary.complete=True；复核 complete=True。

模型：`qwen3:4b-instruct`；digest：`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
量化：`Q4_K_M`；Ollama：`0.34.4`。

冻结平台 SHA：`df796059446bf87ae630f144b15dc90ccba2cfe2`；eval SHA：`28264e9364fe5d395eb28eb1e7dc558afbc79fca`。
实验 config_hash：`355cd79a5cd4185fd9093adcd83beee46f956633aa366855a7d31d232a642e91`。

```json
{
  "generation": {
    "context": 6144,
    "output_tokens": 512,
    "timeout": 300.0,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 48000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**grounded**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 0 个 trial / 0 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 1 条。

每条原始 trace：

- [growth-feed/0/grounded](experiments/probe-v2-4b/traces/growth-feed/0/grounded/trace.json)；status=completed；full success=True

## 24 dev 工程 fixture (`release-fixture-dev`)

原始材料：[experiment.json](experiments/release-fixture-dev/experiment.json)、[results.json](experiments/release-fixture-dev/results.json)、[summary.json](experiments/release-fixture-dev/summary.json)、[report.md](experiments/release-fixture-dev/report.md)。

计划 72 条；记录 72 条；summary.complete=True；复核 complete=True。

模型：`Scripted fixture`；digest：`不适用 / 未记录`。
量化：`未记录`；Ollama：`未记录`。

冻结平台 SHA：`df796059446bf87ae630f144b15dc90ccba2cfe2`；eval SHA：`28264e9364fe5d395eb28eb1e7dc558afbc79fca`。
实验 config_hash：`bb49a69b89790c4f92135475e63a2536698f61d7fe7e14039ad7dcd0fd9f144d`。

```json
{
  "generation": {
    "context": 4096,
    "output_tokens": 384,
    "timeout": 180,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 12000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**baseline**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 24 个 trial / 48 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 24 条。

**grounded**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 24 个 trial / 48 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 24 条。

**no-changes**：首个失败 `{"cause_answer": 17, "current_change_evidence": 7}`；全部失败 checks `{"cause_answer": 17, "current_change_evidence": 24, "recommendation_answer": 17, "required_tools": 24, "uncertainty_answer": 17}`。
JSON 解析失败 0 条；未知 provider 用量 24 个 trial / 48 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 24 条。

fixture trace 未随发布复制；按 [fixture 复现命令](../docs/reproduce.md)可重建。公开保留 manifest、results、summary 和 report；这些工程结果不计入模型实测。

## 8 holdout 工程 fixture (`release-fixture-holdout`)

原始材料：[experiment.json](experiments/release-fixture-holdout/experiment.json)、[results.json](experiments/release-fixture-holdout/results.json)、[summary.json](experiments/release-fixture-holdout/summary.json)、[report.md](experiments/release-fixture-holdout/report.md)。

计划 24 条；记录 24 条；summary.complete=True；复核 complete=True。

模型：`Scripted fixture`；digest：`不适用 / 未记录`。
量化：`未记录`；Ollama：`未记录`。

冻结平台 SHA：`df796059446bf87ae630f144b15dc90ccba2cfe2`；eval SHA：`28264e9364fe5d395eb28eb1e7dc558afbc79fca`。
实验 config_hash：`38a64bee0bf17d03dc804fb06e5e1cedeb3e2758e3990a510a51b82847b2491d`。

```json
{
  "generation": {
    "context": 4096,
    "output_tokens": 384,
    "timeout": 180,
    "seed": 42,
    "temperature": 0
  },
  "budgets": {
    "steps": 8,
    "calls": 16,
    "tokens": 12000,
    "context": 60000
  },
  "environment": {
    "python": "3.12.14",
    "os": "Windows",
    "machine": "AMD64",
    "cpu_count": 8
  }
}
```

**baseline**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 8 个 trial / 16 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

**grounded**：首个失败 `{}`；全部失败 checks `{}`。
JSON 解析失败 0 条；未知 provider 用量 8 个 trial / 16 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

**no-changes**：首个失败 `{"cause_answer": 5, "citation_ids": 1, "current_change_evidence": 2}`；全部失败 checks `{"cause_answer": 5, "citation_ids": 1, "current_change_evidence": 8, "recommendation_answer": 5, "required_tools": 8, "uncertainty_answer": 5}`。
JSON 解析失败 0 条；未知 provider 用量 8 个 trial / 16 次请求；缺失 token 字段 0 条、缺失用量计数 0 条、具有 wall/latency 数值 8 条。

fixture trace 未随发布复制；按 [fixture 复现命令](../docs/reproduce.md)可重建。公开保留 manifest、results、summary 和 report；这些工程结果不计入模型实测。

## 指标与结论边界

主 full success 要求结构化决策、真实目标服务观测、当前手册/变更引用、允许工具与无执行错误全部通过。decision_accuracy 只核对结构化决策，是次指标，不证明证据完整或最终任务成功。
baseline/grounded 的提示比较须保持同源码、模型、工具、任务与预算。no-changes 缺少任务契约要求的当前变更工具，主 success 会机械失败；0% 不能被解读为纯推理差距，应另读 cause/recommendation 检查及次级决策字段。
verified 包含操作者 service scope、输出校验及预算内修正，是 tool_scope_and_output_validation 工程处理，不是纯 prompt 对比、SFT 或 Agentic RL。不同配置间不生成配对提升值。
两个 verified dev 回归题由开发错误选出，存在选择偏差，不能作为随机泛化估计；八个公开 holdout 是独立服务检查，任务数很小且公开，不是隐藏生产基准。提示与校验规则在查看 holdout 模型结果前冻结。
Wilson 区间仅作描述；重复 trial 共享任务，正式配对报告按任务聚类 bootstrap。小样本不足以证明显著提升或生产泛化。未知 provider 用量不是零成本；token 总数不能直接当货币成本。
SFT 候选只允许成功真实 dev 轨迹并需人工审核；fixture、holdout 和失败始终排除。本发布没有模型权重训练或 SFT/RL 提升声明。

冻结发布源码已通过平台 77 项测试、eval 35 项测试（31 项完整套件及 4 项评分边界测试）；源码在二次测试前后一致。工程测试通过不能替代模型任务成功。
