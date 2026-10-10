"""LoRA updates to a pretrained causal LM, with constrained token decoding.

The policy is the LM's original vocabulary logits. No trainable router/head or
script chooses a tool. The decoder only normalizes the nine declared actions.
"""
import hashlib
from pathlib import Path

from .environment import ACTION_CODES


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LanguagePolicy:
    def __init__(self, model_path, revision, seed=42, threads=4, max_length=384, lora_rank=4,
                 model_id="HuggingFaceTB/SmolLM2-135M-Instruct"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model
        self.torch = torch
        if not Path(model_path).is_dir():
            raise ValueError("model must be a local pinned snapshot; download separately")
        if not revision or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("a full immutable Hugging Face revision SHA is required")
        if not 1 <= threads <= 8 or not 96 <= max_length <= 1024:
            raise ValueError("invalid CPU threads/context bounds")
        torch.set_num_threads(threads)
        torch.manual_seed(seed)
        self.max_length, self.revision = max_length, revision
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.tokenizer.name_or_path = model_id
        self.tokenizer.init_kwargs["name_or_path"] = model_id
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.tokenizer.truncation_side = "left"
        ids = []
        for code in ACTION_CODES:
            encoded = self.tokenizer.encode(" " + code, add_special_tokens=False)
            if len(encoded) != 1:
                raise ValueError("action must map to one existing vocabulary token: " + code)
            ids.append(encoded[0])
        if len(ids) != len(set(ids)):
            raise ValueError("action token collision")
        self.action_ids = torch.tensor(ids, dtype=torch.long)
        base = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, dtype=torch.float32)
        base.config.use_cache = False
        self.model = get_peft_model(base, LoraConfig(r=lora_rank, lora_alpha=2*lora_rank,
            target_modules=["q_proj", "v_proj"], lora_dropout=0.0, bias="none", task_type="CAUSAL_LM"))
        # Saved adapters identify the reproducible public base, not a host path.
        self.model.peft_config["default"].base_model_name_or_path = model_id
        self.model.peft_config["default"].revision = revision
        self.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        self.model.enable_input_require_grads()
        # Train mode enables gradient checkpointing. Disable every dropout module
        # so sampled rollout and replay use the same policy distribution.
        self.model.train()
        for module in self.model.modules():
            if isinstance(module, torch.nn.Dropout):
                module.eval()
        self.parameters = [parameter for parameter in self.model.parameters() if parameter.requires_grad]
        self.optimizer = torch.optim.AdamW(self.parameters, lr=0.001, weight_decay=0.0)
        self.initial_hash = self.parameter_hash()

    def parameter_hash(self):
        digest = hashlib.sha256()
        for name, parameter in sorted(self.model.named_parameters()):
            if parameter.requires_grad:
                digest.update(name.encode())
                digest.update(parameter.detach().cpu().contiguous().numpy().tobytes())
        return digest.hexdigest()

    def distributions(self, prompts, temperature=1.0):
        if temperature <= 0:
            raise ValueError("temperature must be positive")
        encoded = self.tokenizer(prompts, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
        # Replaying mixed-length padded batches must use the same real-token
        # positions as single-episode sampling, independent of left-pad width.
        encoded["position_ids"] = encoded["attention_mask"].cumsum(dim=-1) - 1
        encoded["position_ids"].masked_fill_(encoded["attention_mask"] == 0, 0)
        original = self.tokenizer(prompts, add_special_tokens=True)["input_ids"]
        lengths = encoded["attention_mask"].sum(dim=1).tolist()
        contexts = [{"input_tokens": int(length), "original_tokens": len(ids), "clipped": len(ids) > length,
                     "max_length": self.max_length, "truncation_side": "left"}
                    for ids, length in zip(original, lengths)]
        # Context clipping is logged explicitly; no hidden label enters inputs.
        # This policy only supervises the next action. Computing just the last
        # position avoids materializing [batch, context, vocabulary] LM logits.
        logits = self.model(**encoded, logits_to_keep=1).logits[:, -1, self.action_ids] / temperature
        return self.torch.distributions.Categorical(logits=logits), contexts

    def act(self, prompt, sample=False, temperature=1.0):
        with self.torch.no_grad():
            distribution, contexts = self.distributions([prompt], temperature)
            index = distribution.sample() if sample else distribution.probs.argmax(dim=-1)
        return ACTION_CODES[int(index[0])], contexts[0]["input_tokens"], distribution.probs[0].tolist(), contexts[0]

    def supervised_step(self, rows, learning_rate=0.001):
        torch = self.torch
        self.optimizer.param_groups[0]["lr"] = learning_rate
        self.optimizer.zero_grad(set_to_none=True)
        distribution, contexts = self.distributions([row["prompt"] for row in rows])
        targets = torch.tensor([ACTION_CODES.index(row["action"]) for row in rows])
        loss = -distribution.log_prob(targets).mean()
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(self.parameters, 1.0)
        self.optimizer.step()
        return {"loss": float(loss.detach()), "gradient_norm": float(norm), "contexts": contexts}

    def begin_reinforce(self, learning_rate=0.0001):
        # SFT optimizer momentum must not masquerade as an RL reward update.
        self.optimizer = self.torch.optim.AdamW(self.parameters, lr=learning_rate, weight_decay=0.0)

    def reinforce_step(self, rollouts, learning_rate=0.0001, entropy_weight=0.0, batch_size=4):
        """On-policy REINFORCE with a leave-one-out group reward baseline.

        Rollouts must be sampled before this update using the current weights.
        Each prompt/action is replayed with gradients; no router or reward model
        weights replace the causal LM. This is not PPO, GRPO, or Qwen training.
        """
        torch = self.torch
        if len(rollouts) < 2:
            raise ValueError("at least two on-policy rollouts are required")
        rewards = [row["episode"]["reward"] for row in rollouts]
        advantages = [reward - (sum(rewards)-reward)/(len(rewards)-1) for reward in rewards]
        states = [(state, advantage) for rollout, advantage in zip(rollouts, advantages) for state in rollout["states"]]
        if not states:
            raise ValueError("empty rollout")
        self.optimizer.param_groups[0]["lr"] = learning_rate
        self.optimizer.zero_grad(set_to_none=True)
        total_loss, total_entropy = 0.0, 0.0
        before_hash = self.parameter_hash()
        for start in range(0, len(states), batch_size):
            chunk = states[start:start + batch_size]
            distribution, _ = self.distributions([item[0]["prompt"] for item in chunk])
            actions = torch.tensor([ACTION_CODES.index(item[0]["action"]) for item in chunk])
            advantage = torch.tensor([item[1] for item in chunk])
            log_probs, entropy = distribution.log_prob(actions), distribution.entropy()
            # Fixed episode count preserves the episode-reward objective.
            # Dividing by sampled state count would add action-dependent length bias.
            loss = (-(advantage * log_probs).sum() - entropy_weight * entropy.sum()) / len(rollouts)
            loss.backward()
            total_loss += float(loss.detach())
            total_entropy += float(entropy.detach().sum()) / len(states)
        norm = torch.nn.utils.clip_grad_norm_(self.parameters, 1.0)
        self.optimizer.step()
        after_hash = self.parameter_hash()
        return {"loss": total_loss, "entropy": total_entropy, "gradient_norm": float(norm),
                "rewards": rewards, "advantages": advantages, "states": len(states),
                "parameter_sha256_before": before_hash, "parameter_sha256_after": after_hash,
                "parameters_changed": before_hash != after_hash,
                "reward_gradient_active": any(abs(value) > 1e-9 for value in advantages) and float(norm) > 0,
                "entropy_weight": entropy_weight, "loss_normalization": "fixed episode count",
                "episodes": len(rollouts)}

    def save(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        # Embeddings are frozen and unchanged. Explicit False also avoids a hub
        # lookup of a remote base configuration during offline adapter saving.
        self.model.save_pretrained(directory, safe_serialization=True, save_embedding_layers=False)
        self.tokenizer.save_pretrained(directory)
        files = {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
                 for path in sorted(directory.iterdir()) if path.is_file()}
        return {"parameter_sha256": self.parameter_hash(), "files": files,
                "trainable_parameters": sum(parameter.numel() for parameter in self.parameters),
                "format": "PEFT LoRA adapter; load with the pinned SmolLM2 base model"}

    def reload_adapter(self, directory):
        """Perturb every adapter tensor, reload, and require exact restoration.

        Merely loading back into already-identical weights would allow an
        incomplete/no-op loader to masquerade as a successful round trip.
        This method verifies the checkpoint just saved from the active adapter.
        """
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        state = load_file(str(Path(directory) / "adapter_model.safetensors"))
        expected = self.parameter_hash()
        with self.torch.no_grad():
            for parameter in self.parameters:
                parameter.add_(0.123)
        if self.parameter_hash() == expected:
            raise ValueError("adapter round-trip test failed to perturb parameters")
        set_peft_model_state_dict(self.model, state, adapter_name="default")
        restored = self.parameter_hash()
        if restored != expected:
            raise ValueError("saved adapter did not exactly restore the perturbed parameters")
        return restored
