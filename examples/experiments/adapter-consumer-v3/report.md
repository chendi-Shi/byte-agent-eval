# Saved adapter consumer evaluation

Loads the pinned base and published LoRA tensors, verifies actual file and parameter hashes, and executes the same constrained policy with actual read-only tools. No training/optimizer steps or model downloads occur.

| Split | Episodes | Full contract successes with renderer | All three tools observed |
|---|---:|---:|---:|
| dev | 6 | 2 | 6 |
| holdout | 8 | 3 | 8 |

Parameter hash unchanged: `true`. Original task order/actions/decisions/all oracle checks reproduce: `true`. Timing and floating probabilities are not asserted equal.
