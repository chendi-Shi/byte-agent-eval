"""Optional real autograd/adapter tests on a tiny random LM, never performance data."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from byte_eval.training.policy import LanguagePolicy

HAS_TRAINING = all(importlib.util.find_spec(name) for name in ("torch", "transformers", "peft", "safetensors"))


@unittest.skipUnless(HAS_TRAINING, "optional training dependencies are not installed")
class LanguagePolicyTests(unittest.TestCase):
    def setUp(self):
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        vocabulary = {word: index for index, word in enumerate(["[UNK]", "[PAD]", "[EOS]", *"ABCDEFGHI", "Next", "action"])}
        tokenizer = Tokenizer(WordLevel(vocabulary, unk_token="[UNK]"))
        tokenizer.pre_tokenizer = Whitespace()
        fast = PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]", pad_token="[PAD]", eos_token="[EOS]")
        fast.save_pretrained(self.root)
        model = LlamaForCausalLM(LlamaConfig(vocab_size=len(vocabulary), hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2, max_position_embeddings=512,
            attention_dropout=0.0, pad_token_id=1, eos_token_id=2))
        model.save_pretrained(self.root, safe_serialization=True)
        self.policy = LanguagePolicy(self.root, "0"*40, threads=1, max_length=96, lora_rank=2, model_id="random-tiny-unit-test")

    def tearDown(self):
        del self.policy
        self.temp.cleanup()

    def test_sft_updates_transformer_weights_and_reload_is_exact(self):
        before = self.policy.parameter_hash()
        details = self.policy.supervised_step([{"prompt": "Next action", "action": "A"}])
        self.assertGreater(details["gradient_norm"], 0)
        self.assertNotEqual(before, self.policy.parameter_hash())
        saved = self.policy.save(self.root / "adapter")
        self.assertEqual(saved["parameter_sha256"], self.policy.reload_adapter(self.root / "adapter"))

    def test_reinforce_reward_update_has_real_autograd_and_clipping_is_recorded(self):
        self.policy.begin_reinforce()
        prompt = " ".join(["Next"] * 120)
        _, tokens, _, context = self.policy.act(prompt)
        self.assertTrue(context["clipped"])
        self.assertEqual(tokens, 96)
        self.assertEqual(context["original_tokens"], 120)
        rollouts = [{"states": [{"prompt": "Next action", "action": action}], "episode": {"reward": reward}}
                    for action, reward in (("A", 1.0), ("B", -1.0))]
        result = self.policy.reinforce_step(rollouts)
        self.assertTrue(result["reward_gradient_active"])
        self.assertTrue(result["parameters_changed"])
        self.assertGreater(result["gradient_norm"], 0)

    def test_zero_reward_advantages_cannot_reuse_sft_momentum_as_rl(self):
        self.policy.supervised_step([{"prompt": "Next action", "action": "A"}])
        self.policy.begin_reinforce()
        before = self.policy.parameter_hash()
        rollouts = [{"states": [{"prompt": "Next action", "action": action}], "episode": {"reward": 1.0}}
                    for action in ("A", "B")]
        details = self.policy.reinforce_step(rollouts, entropy_weight=0.0)
        self.assertFalse(details["reward_gradient_active"])
        self.assertEqual(details["gradient_norm"], 0)
        self.assertEqual(before, self.policy.parameter_hash())

    def test_variable_length_rollouts_use_fixed_episode_count(self):
        self.policy.begin_reinforce()
        prompt = "Next action"
        with self.policy.torch.no_grad():
            distribution, _ = self.policy.distributions([prompt])
            log_a = float(distribution.log_prob(self.policy.torch.tensor([0]))[0])
            log_b = float(distribution.log_prob(self.policy.torch.tensor([1]))[0])
        rollouts = [
            {"states": [{"prompt": prompt, "action": "A"}, {"prompt": prompt, "action": "A"}], "episode": {"reward": 1.0}},
            {"states": [{"prompt": prompt, "action": "B"}], "episode": {"reward": -1.0}},
        ]
        expected = -(2.0 * (log_a + log_a) - 2.0 * log_b) / 2.0
        result = self.policy.reinforce_step(rollouts, entropy_weight=0.0)
        self.assertAlmostEqual(result["loss"], expected, places=5)
        self.assertEqual(result["episodes"], 2)

    def test_noop_adapter_loader_cannot_pass_roundtrip(self):
        self.policy.save(self.root / "adapter")
        with patch("peft.set_peft_model_state_dict", return_value=None):
            with self.assertRaisesRegex(ValueError, "exactly restore"):
                self.policy.reload_adapter(self.root / "adapter")

    def test_last_position_logits_match_full_sequence_action_distribution(self):
        prompt = "Next action A B C"
        encoded = self.policy.tokenizer([prompt], return_tensors="pt")
        with self.policy.torch.no_grad():
            full = self.policy.model(**encoded).logits[:, -1, self.policy.action_ids]
            distribution, _ = self.policy.distributions([prompt])
            expected = self.policy.torch.softmax(full, dim=-1)
        self.policy.torch.testing.assert_close(distribution.probs, expected, atol=1e-6, rtol=1e-5)

    def test_single_sampling_and_mixed_length_batch_replay_match(self):
        prompt = "Next action"
        with self.policy.torch.no_grad():
            single, _ = self.policy.distributions([prompt])
            batch, contexts = self.policy.distributions([prompt, "Next action A B C Next action Next"])
        self.assertEqual(contexts[0]["input_tokens"], 2)
        self.policy.torch.testing.assert_close(single.probs[0], batch.probs[0], atol=1e-6, rtol=1e-5)


if __name__ == "__main__":
    unittest.main()
