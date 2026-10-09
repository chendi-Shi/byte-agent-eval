# Agent evaluation

ENGINEERING FIXTURES — NOT MODEL PERFORMANCE

Split: holdout. Recorded 24 / 24 planned trials. Experiment complete: True.

| Profile | Kind | Trials | Successes | Success rate | Decision accuracy (secondary) | Unknown usage | Parse failures | Median wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | prompt_baseline | 8 | 8 | 100.0% | 100.0% | 8 | 0 | 0.14 |
| grounded | prompt_treatment | 8 | 8 | 100.0% | 100.0% | 8 | 0 | 0.14 |
| no-changes | causal_tool_ablation | 8 | 0 | 0.0% | 37.5% | 8 | 0 | 0.12 |

Excluded fixture trials: 0.

Prompt comparison (same tools/budgets), task-clustered bootstrap: {"profiles": ["baseline", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 0.0, "bootstrap95": [0.0, 0.0]}

Causal tool ablation (different available tools; not a prompt comparison): {"profiles": ["no-changes", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 1.0, "bootstrap95": [1.0, 1.0]}

Secondary decision-field ablation (ignores evidence completeness, never replaces task success): {"profiles": ["no-changes", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 0.625, "bootstrap95": [0.25, 0.875]}

Ablation task success requires the same complete evidence as the full-tool task, so missing incident_changes mechanically fails that check. Use exact decision-field accuracy as a secondary diagnostic and inspect cause/recommendation failures; do not claim the completeness delta proves improved reasoning.

First failures and all check failures: {"baseline": {"first": {}, "checks": {"allowed_tools": 0, "cause_answer": 0, "citation_ids": 0, "completed": 0, "current_change_evidence": 0, "current_metrics": 0, "metric_status_consistency": 0, "metrics_observed": 0, "no_tool_errors": 0, "numeric_answer": 0, "recommendation_answer": 0, "required_tools": 0, "runbook_evidence": 0, "service_answer": 0, "service_scoped_calls": 0, "status_answer": 0, "structured_answer": 0, "uncertainty_answer": 0}}, "grounded": {"first": {}, "checks": {"allowed_tools": 0, "cause_answer": 0, "citation_ids": 0, "completed": 0, "current_change_evidence": 0, "current_metrics": 0, "metric_status_consistency": 0, "metrics_observed": 0, "no_tool_errors": 0, "numeric_answer": 0, "recommendation_answer": 0, "required_tools": 0, "runbook_evidence": 0, "service_answer": 0, "service_scoped_calls": 0, "status_answer": 0, "structured_answer": 0, "uncertainty_answer": 0}}, "no-changes": {"first": {"cause_answer": 5, "citation_ids": 1, "current_change_evidence": 2}, "checks": {"allowed_tools": 0, "cause_answer": 5, "citation_ids": 1, "completed": 0, "current_change_evidence": 8, "current_metrics": 0, "metric_status_consistency": 0, "metrics_observed": 0, "no_tool_errors": 0, "numeric_answer": 0, "recommendation_answer": 5, "required_tools": 8, "runbook_evidence": 0, "service_answer": 0, "service_scoped_calls": 0, "status_answer": 0, "structured_answer": 0, "uncertainty_answer": 5}}}

Synthetic incidents; public holdout checks service/scenario isolation, not an unseen production benchmark. Wilson intervals are descriptive; repeated trials share a task, so bootstrap clusters by task. Fixture results validate software only. Missing/unknown token usage is not zero cost. Structured enums and cited current records validate bounded decisions, not arbitrary natural-language reasoning.
