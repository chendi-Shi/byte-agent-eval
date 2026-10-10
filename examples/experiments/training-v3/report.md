# Actual small language-model tool-policy training

This experiment updates SmolLM2 LoRA attention weights through supervised token loss and executed-tool REINFORCE rewards. Its constrained actions and mechanical renderer differ from the free-form Qwen benchmark.

| Stage | Split | Episodes | Full contract successes with renderer | All three tools observed | Mean reward |
|---|---|---:|---:|---:|---:|
| base | dev | 6 | 0 | 0 | -0.633 |
| base | holdout | 8 | 0 | 0 | -0.450 |
| sft | dev | 6 | 3 | 6 | 0.800 |
| sft | holdout | 8 | 3 | 8 | 0.675 |
| reinforce | dev | 6 | 2 | 6 | 0.633 |
| reinforce | holdout | 8 | 3 | 8 | 0.675 |

Weight/reload checks: `{"sft_weights_changed": true, "sft_reload_exact": true, "rl_weights_changed": true, "rl_reward_gradient_active": true, "rl_reload_exact": true}`. No improvement is assumed. All evaluation failures and RL sampled actions/rewards remain in the trace files. The public eight-task test set is evaluation only; this is not an unseen production result.
