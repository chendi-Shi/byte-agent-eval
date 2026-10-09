# Agent evaluation

MODEL RUNS — SYNTHETIC INCIDENT SUITE

Split: dev. Recorded 24 / 24 planned trials. Experiment complete: False.

| Profile | Kind | Trials | Successes | Success rate | Decision accuracy (secondary) | Unknown usage | Parse failures | Median wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | prompt_baseline | 8 | 2 | 25.0% | 25.0% | 0 | 1 | 189.23 |
| grounded | prompt_treatment | 8 | 4 | 50.0% | 50.0% | 0 | 2 | 252.48 |
| no-changes | causal_tool_ablation | 8 | 0 | 0.0% | 12.5% | 1 | 2 | 179.46 |

Excluded fixture trials: 0.

INTERRUPTED: {"reason": "provider_uncertain", "task_id": "growth-invite", "profile": "no-changes", "recorded_trials": 24, "planned_trials": 24, "at": "2026-10-09T03:51:25.508393+00:00"}

Prompt comparison (same tools/budgets), task-clustered bootstrap: {"profiles": ["baseline", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 0.25, "bootstrap95": [0.0, 0.5]}

Causal tool ablation (different available tools; not a prompt comparison): {"profiles": ["no-changes", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 0.5, "bootstrap95": [0.125, 0.875]}

Secondary decision-field ablation (ignores evidence completeness, never replaces task success): {"profiles": ["no-changes", "grounded"], "paired_tasks": 8, "paired_trials": 8, "missing_pair_trials": 0, "missing_pairs": [], "delta": 0.375, "bootstrap95": [0.0, 0.75]}

Ablation task success requires the same complete evidence as the full-tool task, so missing incident_changes mechanically fails that check. Use exact decision-field accuracy as a secondary diagnostic and inspect cause/recommendation failures; do not claim the completeness delta proves improved reasoning.

First failures and all check failures: {"baseline": {"first": {"numeric_answer": 3, "structured_answer": 1, "uncertainty_answer": 2}, "checks": {"allowed_tools": 0, "cause_answer": 3, "citation_ids": 1, "completed": 0, "current_change_evidence": 1, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "no_tool_errors": 0, "numeric_answer": 4, "recommendation_answer": 3, "required_tools": 1, "runbook_evidence": 1, "service_answer": 1, "service_scoped_calls": 1, "status_answer": 1, "structured_answer": 1, "uncertainty_answer": 5}}, "grounded": {"first": {"numeric_answer": 2, "structured_answer": 2}, "checks": {"allowed_tools": 0, "cause_answer": 2, "citation_ids": 2, "completed": 0, "current_change_evidence": 2, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "no_tool_errors": 0, "numeric_answer": 4, "recommendation_answer": 2, "required_tools": 1, "runbook_evidence": 2, "service_answer": 2, "service_scoped_calls": 1, "status_answer": 2, "structured_answer": 2, "uncertainty_answer": 2}}, "no-changes": {"first": {"cause_answer": 2, "completed": 1, "current_change_evidence": 1, "numeric_answer": 2, "structured_answer": 1, "uncertainty_answer": 1}, "checks": {"allowed_tools": 0, "cause_answer": 5, "citation_ids": 2, "completed": 1, "current_change_evidence": 8, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "no_tool_errors": 0, "numeric_answer": 4, "recommendation_answer": 5, "required_tools": 8, "runbook_evidence": 2, "service_answer": 2, "service_scoped_calls": 1, "status_answer": 2, "structured_answer": 2, "uncertainty_answer": 4}}}

Synthetic incidents; public holdout checks service/scenario isolation, not an unseen production benchmark. Wilson intervals are descriptive; repeated trials share a task, so bootstrap clusters by task. Fixture results validate software only. Missing/unknown token usage is not zero cost. Structured enums and cited current records validate bounded decisions, not arbitrary natural-language reasoning.
