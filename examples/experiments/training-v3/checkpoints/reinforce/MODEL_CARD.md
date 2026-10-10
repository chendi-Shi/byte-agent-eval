---
license: apache-2.0
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
library_name: peft
---
# reinforce constrained tool-policy LoRA adapter

Base author: HuggingFaceTB. Base: [HuggingFaceTB/SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct),
pinned revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`. The base model is licensed under Apache License 2.0;
see the publisher's [model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/blob/12fd25f77366fa6b3b4b768ec3050bf629380bac/README.md).
This checkpoint and its base-derived adapter weights use Apache License 2.0,
separately from the repository's MIT license for original application code.

Modification date: 2026-10-09. Stage: `reinforce`. This project's code applies LoRA to
the pretrained model's q_proj/v_proj attention matrices. SFT uses development-only
synthetic tool-action demonstrations; REINFORCE uses actual bounded executed-tool
episode rewards on the same training partition. Initial checkpoints contain the
initial untrained LoRA adapter. Original vocabulary logits choose among nine
action tokens; the host binds service arguments and mechanically renders numeric
measurements, citations and JSON. This is a SmolLM2-135M constrained policy
experiment, not training Qwen or free-form Agent citation generation.

The frozen manifest records 18 training, 6 validation and 8 public synthetic
evaluation tasks. Validation/public evaluation are not training examples. Consult
the original manifest, training log, rollouts, evaluations and weights.json for
actual settings, failures, gradients and parameter/reload checks. No accuracy
improvement, production scale, safety guarantee or human review is assumed.

Base weights and tokenizer copies are not redistributed. Load the tokenizer from
the exact pinned base revision. The published adapter_model.safetensors is the
actual saved binary, with checksums in weights.json and publication-manifest.json.
