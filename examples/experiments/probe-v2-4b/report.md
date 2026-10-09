# Agent evaluation

MODEL RUNS — SYNTHETIC INCIDENT SUITE

Split: dev. Recorded 1 / 1 planned trials. Experiment complete: True.

| Profile | Kind | Trials | Successes | Success rate | Decision accuracy (secondary) | Unknown usage | Parse failures | Median wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| grounded | prompt_treatment | 1 | 1 | 100.0% | 100.0% | 0 | 0 | 311.66 |

Excluded fixture trials: 0.

Prompt comparison (same tools/budgets), task-clustered bootstrap: {"profiles": ["baseline", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "355cd79a5cd4185fd9093adcd83beee46f956633aa366855a7d31d232a642e91", "missing_profiles": ["baseline"]}], "delta": null, "bootstrap95": null}

Causal tool ablation (different available tools; not a prompt comparison): {"profiles": ["no-changes", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "355cd79a5cd4185fd9093adcd83beee46f956633aa366855a7d31d232a642e91", "missing_profiles": ["no-changes"]}], "delta": null, "bootstrap95": null}

Secondary decision-field ablation (ignores evidence completeness, never replaces task success): {"profiles": ["no-changes", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "355cd79a5cd4185fd9093adcd83beee46f956633aa366855a7d31d232a642e91", "missing_profiles": ["no-changes"]}], "delta": null, "bootstrap95": null}

Ablation task success requires the same complete evidence as the full-tool task, so missing incident_changes mechanically fails that check. Use exact decision-field accuracy as a secondary diagnostic and inspect cause/recommendation failures; do not claim the completeness delta proves improved reasoning.

First failures and all check failures: {"grounded": {"first": {}, "checks": {"allowed_tools": 0, "cause_answer": 0, "citation_ids": 0, "completed": 0, "current_change_evidence": 0, "current_metrics": 0, "metric_status_consistency": 0, "metrics_observed": 0, "no_tool_errors": 0, "numeric_answer": 0, "recommendation_answer": 0, "required_tools": 0, "runbook_evidence": 0, "service_answer": 0, "service_scoped_calls": 0, "status_answer": 0, "structured_answer": 0, "uncertainty_answer": 0}}}

Synthetic incidents; public holdout checks service/scenario isolation, not an unseen production benchmark. Wilson intervals are descriptive; repeated trials share a task, so bootstrap clusters by task. Fixture results validate software only. Missing/unknown token usage is not zero cost. Structured enums and cited current records validate bounded decisions, not arbitrary natural-language reasoning.
