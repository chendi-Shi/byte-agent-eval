# Agent evaluation

MODEL RUNS — SYNTHETIC INCIDENT SUITE

Split: dev. Recorded 1 / 1 planned trials. Experiment complete: True.

| Profile | Kind | Trials | Successes | Success rate | Decision accuracy (secondary) | Unknown usage | Parse failures | Median wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| grounded | prompt_treatment | 1 | 0 | 0.0% | 0.0% | 0 | 1 | 24.11 |

Excluded fixture trials: 0.

Prompt comparison (same tools/budgets), task-clustered bootstrap: {"profiles": ["baseline", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "f0d3e28498f1cd1b95764f85f424207acf6da995ced1137c7543029595a9a4fb", "missing_profiles": ["baseline"]}], "delta": null, "bootstrap95": null}

Causal tool ablation (different available tools; not a prompt comparison): {"profiles": ["no-changes", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "f0d3e28498f1cd1b95764f85f424207acf6da995ced1137c7543029595a9a4fb", "missing_profiles": ["no-changes"]}], "delta": null, "bootstrap95": null}

Secondary decision-field ablation (ignores evidence completeness, never replaces task success): {"profiles": ["no-changes", "grounded"], "paired_tasks": 0, "paired_trials": 0, "missing_pair_trials": 1, "missing_pairs": [{"task_id": "growth-feed", "trial": 0, "config_hash": "f0d3e28498f1cd1b95764f85f424207acf6da995ced1137c7543029595a9a4fb", "missing_profiles": ["no-changes"]}], "delta": null, "bootstrap95": null}

Ablation task success requires the same complete evidence as the full-tool task, so missing incident_changes mechanically fails that check. Use exact decision-field accuracy as a secondary diagnostic and inspect cause/recommendation failures; do not claim the completeness delta proves improved reasoning.

First failures and all check failures: {"grounded": {"first": {"structured_answer": 1}, "checks": {"allowed_tools": 0, "cause_answer": 1, "citation_ids": 1, "completed": 0, "current_change_evidence": 1, "current_metrics": 1, "metric_status_consistency": 1, "metrics_observed": 1, "no_tool_errors": 0, "numeric_answer": 1, "recommendation_answer": 1, "required_tools": 1, "runbook_evidence": 1, "service_answer": 1, "service_scoped_calls": 0, "status_answer": 1, "structured_answer": 1, "uncertainty_answer": 1}}}

Synthetic incidents; public holdout checks service/scenario isolation, not an unseen production benchmark. Wilson intervals are descriptive; repeated trials share a task, so bootstrap clusters by task. Fixture results validate software only. Missing/unknown token usage is not zero cost. Structured enums and cited current records validate bounded decisions, not arbitrary natural-language reasoning.
