# Agent evaluation

MODEL RUNS — SYNTHETIC INCIDENT SUITE

Split: dev. Recorded 2 / 2 planned trials. Experiment complete: True.

| Profile | Kind | Trials | Successes | Success rate | Decision accuracy (secondary) | Unknown usage | Parse failures | Median wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| verified | tool_scope_and_output_validation | 2 | 2 | 100.0% | 100.0% | 0 | 0 | 247.35 |

Excluded fixture trials: 0.

Verified is an operator tool-scope and deterministic output-validation treatment, not a pure prompt comparison or LLM training. The validator sees tool observations and schema rules, not benchmark labels; the independent oracle still scores causes/recommendations. Corrections consume the existing budgets; blocked/failed tool calls remain failures. No paired verified-vs-other delta is computed across configurations.

First failures and all check failures: {"verified": {"first": {}, "checks": {"allowed_tools": 0, "cause_answer": 0, "citation_ids": 0, "completed": 0, "current_change_evidence": 0, "current_metrics": 0, "metric_status_consistency": 0, "metrics_observed": 0, "no_tool_errors": 0, "numeric_answer": 0, "recommendation_answer": 0, "required_tools": 0, "runbook_evidence": 0, "service_answer": 0, "service_scoped_calls": 0, "status_answer": 0, "structured_answer": 0, "uncertainty_answer": 0}}}

Synthetic incidents; public holdout checks service/scenario isolation, not an unseen production benchmark. Wilson intervals are descriptive; repeated trials share a task, so bootstrap clusters by task. Fixture results validate software only. Missing/unknown token usage is not zero cost. Structured enums and cited current records validate bounded decisions, not arbitrary natural-language reasoning.
