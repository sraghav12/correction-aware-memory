"""Optional native API check uses random tiny weights, never Hub downloads."""

import importlib.util
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="optional ml extra is absent")
def test_native_qwen_api_and_backward_probe():
    code = '''
import json, socket, types
def forbidden(*args, **kwargs):
    raise AssertionError("native API check attempted network access")
socket.socket.connect = forbidden
socket.create_connection = forbidden
import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from cam.models import HuggingFaceRuntime, GenerationConfig

class Tokenizer:
    eos_token_id = 2
    def __call__(self, *args, **kwargs):
        return {"input_ids": torch.tensor([[3, 4, 5, 6]])}
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["enable_thinking"] is False and kwargs["truncation"] is False
        return self()
    def decode(self, tokens, **kwargs):
        return json.dumps(tokens.tolist())

config = Qwen3Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                    num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                    head_dim=8, eos_token_id=2, pad_token_id=2)
devices = ["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])
for device in devices:
    runtime = HuggingFaceRuntime.__new__(HuggingFaceRuntime)
    runtime.torch, runtime.device, runtime.tokenizer = torch, device, Tokenizer()
    runtime.model = Qwen3ForCausalLM(config).to(device).eval()
    prepared = runtime.prepare([{"role":"user", "content":"probe"}])
    output = runtime.generate(prepared, GenerationConfig(max_new_tokens=4))
    assert 1 <= output.output_tokens <= 4
    probe = runtime.probe_backward()
    assert probe["status"] == "passed", probe
    assert probe["weights_updated"] is False
    assert all(p.grad is None for p in runtime.model.parameters())
    print(device, "random-tiny-Qwen3 forward/backward API passed")

class Nonfinite(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.p = torch.nn.Parameter(torch.tensor([1.]))
    def forward(self, **kwargs):
        return types.SimpleNamespace(loss=(self.p * float("nan")).sum())
runtime.model = Nonfinite()
runtime.device = "cpu"
probe = runtime.probe_backward()
assert probe["status"] == "failed"
json.dumps(probe, allow_nan=False)
'''
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
