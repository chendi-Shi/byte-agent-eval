# Small language-model SFT and executed-tool RL

This optional experiment trains `HuggingFaceTB/SmolLM2-135M-Instruct` attention
LoRA weights on CPU. It is a separate bounded tool-policy experiment. It does
not train the Qwen3 4B model used by the original incident evaluation and does
not claim equal capability or comparable task success rates.

## What the language model actually learns

The pretrained causal LM computes its normal vocabulary logits. A constrained
decoder normalizes nine existing single-token actions: three actions execute
the real `service_metrics`, `knowledge_search`, and `incident_changes` tools;
six terminate with a diagnosis. LoRA rank 4 changes the transformer's `q_proj`
and `v_proj` parameters. There is no separately trained classification router
and no script picking actions instead of the model.

Each episode has at most four actions and can terminate earlier. The operator fixes the service, query, metric
window, and validated tool arguments. The host summarizes actual numeric
observations, extracts thresholds from returned policy text, and preserves
actual change kind/status/minute. It does not infer the diagnosis. After the
model chooses a diagnosis token, a mechanical renderer copies observed metric
values and actual citation IDs into the fixed JSON schema. This simplifies
argument generation, arbitrary JSON generation, and untrusted text handling;
success is labelled **constrained policy plus renderer**, never free-form agent
performance. The policy prompt contains no evaluator diagnosis labels.

## Training data and isolation

Before model evaluation, `partition.json` freezes 18 development training
services, 6 distinct development validation services, and 8 public holdout
services. The six validation IDs are explicit constants in `environment.py`.
Training demonstrations are 72 action decisions (18 four-action paths).
Their label is **synthetic-supervised**: development oracle labels supply
teacher diagnoses and actual tools supply observations. They are not presented
as model-generated trajectories.

The eight original successful Qwen development candidates receive automated
checksum, message equality, configuration, development-only, non-fixture,
completion, and independent oracle checks. `candidate-review.json` preserves
`human_review_required: true` and `human_review_complete: false`. Their long
chat transcripts are excluded from this tiny policy's training corpus.

The validation and holdout services never enter SFT or RL. Base, SFT, and RL
greedy evaluations use the same frozen 14 evaluation tasks and action/renderer
contract. The holdout is already public, so it measures service isolation in a
synthetic suite rather than unseen production generalization. Hyperparameters
must be fixed before inspecting holdout results; poor or unchanged scores are
valid results, not permission to retune on the test set.

## Actual optimization

SFT minimizes conditional cross entropy for the teacher action among the nine
legal original-vocabulary tokens. Loss and gradient norms are recorded per
update. CPU execution uses FP32, four threads, gradient checkpointing, and
bounded prompt lengths.
Only the last position's language-head logits are computed (`logits_to_keep=1`),
which preserves the next-action distribution while avoiding a full
batch-by-context-by-vocabulary tensor. The optional dependencies require
Transformers 4.57+ for this Llama forward interface.
Left-padding position IDs are computed from each attention mask, so rollout
sampling and mixed-length batch replay use the same real-token positions.

RL samples four multi-step episodes on the same training service from the
current LM. Tools really execute. Terminal reward grants 0.1 per distinct
successful tool, penalizes each tool event beyond distinct successful tools
(including duplicates and failed calls) by 0.1, grants 1.0 for independent
full contract success (otherwise 0.2 for a correct decision), subtracts 0.3 for
missing required tools, and subtracts 0.2 for no final decision. The independent
oracle sees the trace after execution; an uncalled tool grants no evidence.

On-policy REINFORCE replays the sampled prompts/actions with gradients. Each
episode's advantage is its reward minus the mean reward of the other episodes
in its group. The update minimizes negative advantage-weighted action log
probability. An optional entropy bonus defaults to zero, so the recorded default
update must come from executed-tool rewards. The optimizer is reset at the RL
boundary to discard SFT momentum. This is **REINFORCE**, not PPO or GRPO.
The action log probabilities are summed within each episode and divided by the
fixed number of sampled episodes, not the action-dependent number of states.
`reward_gradient_active_steps` must be positive to mark an actual RL experiment
complete; an entropy-only parameter change is insufficient evidence.

The runner saves initial, SFT, and RL `save_pretrained` PEFT adapters. Each has
file SHA-256 hashes and trainable parameter hashes. The SFT and RL checkpoints
also have load-round-trip checks; the initial checkpoint is saved and hashed.
For a round trip, every trainable adapter tensor is deliberately perturbed
before loading; a no-op or incomplete loader cannot pass by preserving the
already-matching in-memory values.
Completion requires changed SFT/RL parameter hashes, exact reload hashes, and
nonzero RL reward advantages. The pinned base model revision, base weight file
hashes, source code hashes, Python/dependency versions, partition hash, seed,
steps, and budgets appear in `manifest.json`.

When the local snapshot includes `download-manifest.json`, the runner checks
its declared repository/revision and every listed file's checksum/size before
loading. The report calls this a verified local download receipt, not a signed
publisher attestation. Without a receipt it records operator-declared
provenance explicitly. Saved adapter configuration uses the official base ID
and immutable revision instead of a local workspace path. Public checkpoint
packages may omit repeated tokenizer files because loading uses that pinned
base tokenizer.

## Run it

Use Python 3.11+ (the completed experiment used Python 3.12) and install the
platform and eval projects, then install CPU PyTorch and the locked optional
dependencies. Run these commands from the eval repository. The training runner
loads local files only and refuses implicit model downloads.

[`examples/download_training_model.py`](../examples/download_training_model.py)
downloads only seven files of the official immutable
`HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac`
snapshot (about 271 MB total). It verifies their fixed byte sizes and SHA-256
against the completed experiment's download receipt before committing each
file, then creates a compatible `download-manifest.json`. It uses normal TLS
certificate verification, imports no model runtime, and executes no downloaded
code. These checks pin the experiment's bytes; they are not publisher signatures.
Existing unexpected files or receipts are rejected rather than overwritten.
`--verify-only` reads the seven local files and receipt without network or writes.

```sh
python -m pip install torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-training.txt -r requirements-training-lock.txt
python -m pip install -e ../byte-agent-platform -e .
python examples/download_training_model.py
python examples/download_training_model.py --verify-only
byte-agent dataset --data runs/training-data
python examples/train_policy.py --model .deps/models/SmolLM2-135M-Instruct/12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac --dataset runs/training-data/services.json \
  --output runs/training-benchmark --benchmark-only --sft-steps 1 --batch-size 2 \
  --rl-steps 0
python examples/train_policy.py --model .deps/models/SmolLM2-135M-Instruct/12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac --dataset runs/training-data/services.json \
  --output runs/training-full --sft-steps 72 --rl-steps 8 --batch-size 4 \
  --review-experiment examples/experiments/release-dev \
  --review-experiment examples/experiments/release-verified-dev
```

Use a new output directory for each experiment. Interrupted runs write an
explicit failure record and preserve completed updates; they are not promoted
to complete experiments. `report.md`, `summary.json`, stage evaluations, all
model action probabilities/prompts, actual tool traces, RL rewards, and adapter
hashes make results inspectable. Saved adapters load using
`PeftModel.from_pretrained(pinned_base_model, checkpoint_directory)`.

The formal run uses 72 SFT optimizer updates, batch size four, and eight RL
group updates with four sampled episodes each. The training corpus's 72
demonstration rows and the 72 optimizer updates are separate counts. These
settings were fixed before evaluating the 14 validation/public-test tasks.

Official references: [SmolLM2 model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct),
[PEFT LoRA](https://huggingface.co/docs/peft/main/en/package_reference/lora),
[PyTorch policy-gradient distributions example](https://docs.pytorch.org/docs/stable/distributions.html).

## Reuse a published adapter without retraining

[`examples/evaluate_adapter.py`](../examples/evaluate_adapter.py) loads an
`initial`, `sft`, or `reinforce` checkpoint into the same nine-token language
policy and executes actual tools. Use the pinned local base snapshot and its
tokenizer; published checkpoints only need `adapter_model.safetensors`,
`adapter_config.json`, and `weights.json`. No model download, optimizer update,
or fallback scripted/random policy runs during evaluation.

```sh
byte-agent dataset --data runs/adapter-evaluation-data
python examples/evaluate_adapter.py --model /path/to/pinned/snapshot \
  --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --checkpoint examples/experiments/training-v3/checkpoints/reinforce \
  --dataset runs/adapter-evaluation-data/services.json \
  --output runs/adapter-consumer --split all \
  --reference examples/experiments/training-v3/reinforce-evaluation.json
```

The consumer verifies base ID, immutable revision, rank, alpha, q/v modules,
adapter/config file bytes and SHA-256, and the loaded trainable parameter hash
against checkpoint metadata. Default CPU settings are the formal experiment's
four threads, seed 42, max length 384, and rank 4. `--split validation` runs the
six frozen development validation services, `--split holdout` runs the eight
public test services, and `--split all` runs the original 14-task order.

An optional `--reference` compares task order, actions, parsed decisions,
success, and every independent oracle check with the original stage evaluation.
Matching all 14 tasks means reproducing both the original successes and its
failures, not passing all 14 business tasks. Read the separate per-split
`full_contract_successes_with_renderer` counts to assess task success.
It does not assert identical latency or every floating model probability.
New manifests, trace files, evaluations, and `summary.json` preserve actual
results and prove the parameter hash remained unchanged. Use a new output
directory; the script refuses to overwrite an existing experiment. These
consumer results still measure a constrained policy plus renderer, not the
free-form Qwen benchmark.

The completed independent RL-adapter consumer is recorded in
[`adapter-consumer-v3/report.md`](../examples/experiments/adapter-consumer-v3/report.md)
and [`summary.json`](../examples/experiments/adapter-consumer-v3/summary.json).
It loaded the published parameter hash, left parameters unchanged, and matched
the reference outcomes for all 14 tasks. Business full-contract success remained
2/6 validation and 3/8 public holdout; matching failures is part of reproduction.
If selecting a checkpoint using development validation, keep the SFT checkpoint
(3/6) ahead of this RL checkpoint (2/6). This selection does not alter the frozen
experiment or justify tuning on public holdout results.

## Preserve the completed training's frozen source binding

The completed training used platform source commit
`10957dfa69c7a2fd33cf12e30066ace883927f9a` and eval source commit
`24717de469c2e75223f2c1fa3b853a35a8e98fb2`. A later independent Multi-Agent
metrics citation repair uses platform commit
`22ad55f82a86d59fda7cd940b669dbf93609d834`; its raw-byte provenance is in
[`examples/multiagent-source-v4.json`](../examples/multiagent-source-v4.json).
That later repair was not part of the training run, and the original training
manifest's 26 source hashes must remain unchanged.
The subsequent V5 prompt clarifications, V6 observation-consistency/model
metadata repair and V7 observed-citation binding are likewise independent of
training. Their raw-byte provenance is preserved in
[`examples/acceptance-source-v6.json`](../examples/acceptance-source-v6.json) and
[`examples/acceptance-source-v7.json`](../examples/acceptance-source-v7.json).
Load the historical archived sources when reproducing the saved policy; do not
replace the completed training's source hashes with those later implementations.

Each repository includes its own `examples/training-source-v3/src` archive:
16 platform Python files and 10 eval Python files matching the training
checkpoints. To consume the saved adapter using those exact source hashes,
place these archives ahead of the current installed projects in `PYTHONPATH`.
Run the following from the eval repository before the consumer command above.

```sh
export PYTHONPATH="examples/training-source-v3/src:../byte-agent-platform/examples/training-source-v3/src"
```

PowerShell uses the platform's path separator:

```powershell
$env:PYTHONPATH = (Resolve-Path examples/training-source-v3/src).Path + [IO.Path]::PathSeparator + (Resolve-Path ../byte-agent-platform/examples/training-source-v3/src).Path
```

The public consumer remains an additional example outside the original
training source checkpoint. Its manifest records its own script hash and the
actually imported package source hashes. Confirm all 26 imported hashes match
the original training manifest; do not replace historical hashes with the
latest Multi-Agent implementation or describe a reference-result match as a
new model-quality improvement.
