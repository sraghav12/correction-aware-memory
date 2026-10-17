from dataclasses import asdict
import importlib.util
import json
import subprocess
import sys

import pytest

from cam import contracts as c, data, models, train
from conftest import make_observation, make_proposal


REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def config(tmp_path, **kwargs):
    assert callable(getattr(c, "TrainConfig", None)), "typed training config is missing"
    return c.TrainConfig(c.DataConfig(split="train"), tmp_path / "adapter", models.ModelConfig(revision=REVISION), **kwargs)


def example():
    observation = c.parse_observation(make_observation())
    return c.DecisionRequest(observation, 0, ()), c.parse_proposal(make_proposal(asdict(observation)))


class Tokenizer:
    eos_token_id = 2

    def apply_chat_template(self, messages, **kwargs):
        assert "initial_fact" not in json.dumps(messages)
        assert kwargs["enable_thinking"] is False
        assert kwargs["truncation"] is False
        if kwargs.get("return_dict", True):
            return {"input_ids": [10, 11, 12], "attention_mask": [1, 1, 1]}
        return [10, 11, 12]

    def encode(self, text, **kwargs):
        assert json.loads(text)["action"] == "create"
        assert kwargs["add_special_tokens"] is False
        return [20, 21, 22]


def test_prompt_tokens_have_no_loss():
    assert callable(getattr(train, "completion_example", None)), "completion masking is missing"
    tokens = train.completion_example(Tokenizer(), *example(), max_sequence=2048)
    assert tokens["input_ids"] == [10, 11, 12, 20, 21, 22, 2]
    assert tokens["labels"] == [-100, -100, -100, 20, 21, 22, 2]
    assert tokens["attention_mask"] == [1] * 7


def test_overlength_example_is_rejected_before_trainer():
    assert callable(getattr(train, "completion_example", None)), "length preflight is missing"
    with pytest.raises(c.ContractError, match="CONTEXT_LIMIT"):
        train.completion_example(Tokenizer(), *example(), max_sequence=6)


@pytest.mark.parametrize("split", ["test", "style_transfer", "pilot", "development"])
def test_test_split_training_rejected(tmp_path, split):
    assert callable(getattr(c, "TrainConfig", None)), "training split gate is missing"
    with pytest.raises(c.ContractError, match="train split"):
        c.TrainConfig(c.DataConfig(split=split), tmp_path / "adapter", models.ModelConfig(revision=REVISION))


def test_research_training_gate_is_not_silently_bypassed(tmp_path):
    settings = config(tmp_path)
    assert callable(getattr(train, "train_adapter", None)), "training gate is missing"
    with pytest.raises(c.RuntimeUnavailable, match="gate"):
        train.train_adapter(settings)
    assert not settings.output_dir.exists()


def test_educational_training_preflights_data_before_runtime(tmp_path):
    settings = config(tmp_path, gate="educational_imitation_only")
    assert callable(getattr(train, "train_adapter", None)), "training assembly is missing"
    with pytest.raises(c.ContractError, match="manifest"):
        train.train_adapter(settings)
    assert not settings.output_dir.exists()


def test_missing_training_runtime_is_explicit(tmp_path, monkeypatch):
    import builtins
    training, development = tmp_path / "train", tmp_path / "dev"
    data.generate_dataset(c.DataConfig(split="train", trajectories=20), training)
    data.generate_dataset(c.DataConfig(split="development", trajectories=5), development)
    settings = c.TrainConfig(c.DataConfig(split="train", manifest=training / "manifest.json"), tmp_path / "out",
                            models.ModelConfig(revision=REVISION), development_manifest=development / "manifest.json",
                            gate="educational_imitation_only")
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("optional runtime deliberately absent")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(c.RuntimeUnavailable, match="runtime"):
        train.train_adapter(settings)
    assert not settings.output_dir.exists()


@pytest.mark.parametrize("kwargs", [{"epochs": 4}, {"max_examples": 21}, {"microbatch": 2}, {"gate": "research_training"}])
def test_educational_smoke_stays_bounded(tmp_path, kwargs):
    with pytest.raises(c.ContractError):
        config(tmp_path, **kwargs)


def test_training_config_reuses_shared_model_contract(tmp_path):
    settings = config(tmp_path)
    assert type(settings.model) is c.ModelConfig is models.ModelConfig


def test_training_corpus_is_balanced_and_excludes_future(tmp_path):
    generated = tmp_path / "train"
    data.generate_dataset(c.DataConfig(split="train", trajectories=20), generated)
    assert callable(getattr(train, "training_corpus", None)), "training snapshot selection is missing"
    manifest, rows = train.training_corpus(generated / "manifest.json", max_examples=20)
    assert manifest["split"] == "train" and len(rows) == 20
    for action in ("create", "reinforce", "supersede", "update", "no_op"):
        assert sum(row["target"].action == action for row in rows) == 4
    for row in rows:
        request = row["request"]
        assert all(ref.observed_at <= request.observation.observed_at for v in request.candidate_versions for ref in v.source_refs)
        assert all(request.observation.observation_id not in v.observation_ids for v in request.candidate_versions)


def test_generation_retains_exact_tokens_for_reload_proof():
    output = models.GenerationOutput("{}", 2)
    assert hasattr(output, "token_ids"), "exact token IDs are missing for reload verification"


@pytest.mark.skipif(importlib.util.find_spec("peft") is None, reason="optional PEFT extra is absent")
def test_base_weights_frozen_and_adapter_reload_matches_saved_output(tmp_path):
    code = r'''
import copy, json, socket, sys
import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from peft import PeftModel
from cam import contracts as c
from cam.train import configure_lora, parameter_digest, optimize
from cam.models import ModelConfig
from pathlib import Path
def forbidden(*args, **kwargs):
    raise AssertionError("native adapter check attempted network")
socket.socket.connect = forbidden
torch.manual_seed(11)
settings=c.TrainConfig(c.DataConfig(split="train"),Path(sys.argv[1]),ModelConfig(revision="c1899de289a04d12100db370d81485cdf75e47ca"),gate="educational_imitation_only")
cfg=Qwen3Config(vocab_size=32,hidden_size=16,intermediate_size=32,num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=8,eos_token_id=2,pad_token_id=2)
base=Qwen3ForCausalLM(cfg)
state=copy.deepcopy(base.state_dict())
model=configure_lora(base,settings)
assert all(not p.requires_grad for name,p in model.named_parameters() if "lora_" not in name)
before=parameter_digest(model,adapter=False)
adapter_before=parameter_digest(model,adapter=True)
items=[{"input_ids":[3,4,5,6],"attention_mask":[1,1,1,1],"labels":[-100,-100,5,6]} for _ in range(2)]
losses=optimize(model,items,settings,torch)
assert parameter_digest(model,adapter=False)==before
assert parameter_digest(model,adapter=True)!=adapter_before
assert losses and all(row["optimizer_steps"]>0 for row in losses)
model.eval()
inputs=torch.tensor([[3,4]])
with torch.inference_mode():
    expected=model.generate(inputs,max_new_tokens=4,do_sample=False)
model.save_pretrained(sys.argv[1],safe_serialization=True)
fresh=Qwen3ForCausalLM(cfg)
fresh.load_state_dict(state)
reloaded=PeftModel.from_pretrained(fresh,sys.argv[1],is_trainable=False,local_files_only=True).eval()
with torch.inference_mode():
    actual=reloaded.generate(inputs,max_new_tokens=4,do_sample=False)
assert expected.tolist()==actual.tolist()
assert parameter_digest(reloaded,adapter=False)==before
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "adapter")], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
