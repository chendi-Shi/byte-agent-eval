# Publication and loading checkpoint `sft`

README.md preserves the original automatically generated PEFT card byte-for-byte;
its checksum is the README.md entry in weights.json. It contains library template
placeholders and the relative local snapshot name originally recorded by PEFT.
Use this PUBLICATION.md for the pinned public base and loading recipe, and
MODEL_CARD.md for actual training scope, attribution and checkpoint licensing.

The checkpoint contains actual PEFT LoRA adapter weights and configuration.
It needs the pinned base model and tokenizer:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
base_id = "HuggingFaceTB/SmolLM2-135M-Instruct"
revision = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
tokenizer = AutoTokenizer.from_pretrained(base_id, revision=revision)
base = AutoModelForCausalLM.from_pretrained(base_id, revision=revision)
model = PeftModel.from_pretrained(base, "path/to/this/checkpoint")
```

The adapter changes vocabulary logits; evaluation uses the nine declared action
tokens and ToolEpisode, not unconstrained model.generate benchmark claims.
See MODEL_CARD.md, LICENSE and NOTICE for separate checkpoint licensing.

Original weights.json remains unchanged and lists all files saved by the trainer.
The adapter, adapter_config.json and original README.md preserve those exact
saved-file hashes. Redundant tokenizer files, merges, vocabulary and chat template
are omitted and loaded from the pinned base instead; their original hashes remain
under omitted_original_saved_files in publication-manifest.json. Newly authored
PUBLICATION.md, MODEL_CARD.md, NOTICE and LICENSE have separate hashes under
publication_documents in that manifest and are outside the trainer's file list.
