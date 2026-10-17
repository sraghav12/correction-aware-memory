from dataclasses import asdict
import json
import os
import subprocess
import sys

import pytest

from cam import contracts as c, models
from cam.store import Store
from conftest import make_observation, make_proposal


REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


class FakeRuntime:
    metadata = {"backend": "fake", "dtype": "fake", "real_model": False}

    def __init__(self, text, tokens=100):
        self.text, self.tokens, self.calls = text, tokens, 0

    def prepare(self, messages):
        return models.PreparedInput(messages, self.tokens)

    def generate(self, prepared, generation):
        self.calls += 1
        return models.GenerationOutput(self.text, 10)

    def probe_backward(self):
        return {"status": "fake", "weights_updated": False}


def build(runtime):
    assert callable(getattr(models, "ModelProposer", None)), "optional model boundary is missing"
    return models.ModelProposer(models.ModelConfig(revision=REVISION), runtime=runtime)


def test_valid_model_output_preserves_raw_and_pin(tmp_path):
    observation = c.parse_observation(make_observation())
    raw = json.dumps(make_proposal(asdict(observation)))
    proposer = build(FakeRuntime(raw))
    with Store(tmp_path / "memory.sqlite") as store:
        request = store.snapshot(observation)
        assert store.commit(request, proposer.propose(request)).status == "committed"
    assert proposer.last_metadata["raw_output"] == raw
    assert proposer.last_metadata["revision"] == REVISION
    assert proposer.last_metadata["input_tokens"] == 100
    assert len(proposer.last_metadata["prompt_sha256"]) == 64


@pytest.mark.parametrize("raw", ["not JSON", '```json\n{}\n```', '{"action": "create"}', 'null'])
def test_malformed_json_rejected_without_repair(raw):
    proposer = build(FakeRuntime(raw))
    with pytest.raises(c.ContractError, match="MODEL_OUTPUT") as captured:
        proposer.propose(c.DecisionRequest(c.parse_observation(make_observation()), 0, ()))
    assert captured.value.raw_output == raw


def test_unknown_ids_are_rejected_by_shared_commit_guard(tmp_path):
    observation = c.parse_observation(make_observation())
    payload = make_proposal(asdict(observation), action="reinforce", target="v:invented", reason="support")
    proposer = build(FakeRuntime(json.dumps(payload)))
    with Store(tmp_path / "memory.sqlite") as store:
        request = store.snapshot(observation)
        result = store.commit(request, proposer.propose(request))
        assert result.status == "rejected"
        assert "UNKNOWN_TARGET" in result.validation_codes
        assert result.before_revision == result.after_revision


def test_input_overflow_never_calls_generation():
    runtime = FakeRuntime("{}", tokens=2049)
    proposer = build(runtime)
    with pytest.raises(c.ContractError, match="CONTEXT_LIMIT"):
        proposer.propose(c.DecisionRequest(c.parse_observation(make_observation()), 0, ()))
    assert runtime.calls == 0
    assert proposer.last_metadata["input_tokens"] == 2049


def test_duplicate_json_keys_are_rejected():
    payload = json.dumps(make_proposal(make_observation()))
    raw = '{"action":"no_op",' + payload[1:]
    proposer = build(FakeRuntime(raw))
    with pytest.raises(c.ContractError, match="MODEL_OUTPUT"):
        proposer.propose(c.DecisionRequest(c.parse_observation(make_observation()), 0, ()))


@pytest.mark.parametrize("settings", [{"revision": "main"}, {"device": "cuda"}, {"adapter_path": "untrained"}])
def test_invalid_runtime_settings_are_explicit(settings):
    assert callable(getattr(models, "ModelConfig", None)), "model settings validation is missing"
    with pytest.raises(c.ContractError):
        models.ModelConfig(**({"revision": REVISION} | settings))


@pytest.mark.parametrize("settings", [{"enable_thinking": True}, {"do_sample": True}, {"decoding": "constrained"}, {"max_input_tokens": 0}, {"max_new_tokens": 257}])
def test_unimplemented_decoding_is_rejected(settings):
    assert callable(getattr(models, "GenerationConfig", None)), "decoding settings validation is missing"
    with pytest.raises(c.ContractError):
        models.GenerationConfig(**settings)


def test_no_cached_model_is_unavailable(tmp_path):
    # Hub cache constants are read at import time. A fresh process must own this
    # empty cache even when another test has imported Hub or cached real weights.
    env = os.environ | {"HF_HOME": str(tmp_path / "empty-cache"),
                       "HF_HUB_CACHE": str(tmp_path / "empty-cache/hub"), "HF_HUB_OFFLINE": "1"}
    code = f'''
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError("network access attempted")
socket.socket.connect = forbidden
socket.create_connection = forbidden
from cam.models import ModelProposer, ModelConfig
from cam.contracts import RuntimeUnavailable
try:
    ModelProposer(ModelConfig(revision={REVISION!r}))
except RuntimeUnavailable as error:
    print(error)
    sys.exit(3)
'''
    completed = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 3, completed.stdout + completed.stderr
    assert "cached" in completed.stdout or "optional" in completed.stdout


def test_optional_ml_not_imported_by_offline_cli():
    code = "import cam.cli, cam.models, sys; assert not ({'torch','transformers','peft','trl','huggingface_hub'} & sys.modules.keys())"
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_frozen_inference_model_skips_backward_without_touching_weights():
    from types import SimpleNamespace

    class FrozenModel:
        def parameters(self):
            return iter([SimpleNamespace(requires_grad=False)])

        def train(self):
            raise AssertionError("frozen inference model entered training mode")

    runtime = models.HuggingFaceRuntime.__new__(models.HuggingFaceRuntime)
    runtime.model = FrozenModel()
    probe = runtime.probe_backward()
    assert probe["status"] == "skipped"
    assert "inference-only" in probe["reason"]
    assert probe["weights_updated"] is False
    assert probe["tokens"] == 0
    assert probe["seconds"] >= 0


def test_evaluator_preserves_model_errors_and_runtime_identity(tmp_path):
    from cam import data, evaluate as evaluation
    from cam.report import write_report
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=2), generated)
    proposer = build(FakeRuntime("RAW MALFORMED MODEL TEXT"))
    config = c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run",
                         proposer={"kind": "qwen", "revision": REVISION})
    report = evaluation.evaluate(config, proposer=proposer)
    predictions = data.read_jsonl(report.run_dir / "predictions.jsonl")
    assert all(row["raw_output"] == "RAW MALFORMED MODEL TEXT" for row in predictions)
    assert all(row["model_call"]["failure_code"] == "MODEL_OUTPUT" for row in predictions)
    assert report.metrics["invalid_output_rate"]["value"] == 1.0
    assert report.manifest["model_status"] == "fake_runtime"
    assert report.manifest["model"]["revision"] == REVISION
    assert report.metrics["resources"]["model_runtime_evaluated"] is False
    html = write_report(report, report.run_dir / "report").read_text()
    assert "These results measure a deterministic rule system" not in html
    assert "fake_runtime" in html


def test_qwen_cli_uses_model_without_rule_fallback(tmp_path, monkeypatch, capsys):
    from cam import cli, data
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=2), generated)
    config = tmp_path / "base.json"
    config.write_text(json.dumps({"schema_version": 1, "data": {"manifest": str(generated / "manifest.json")},
                                  "proposer": {"kind": "qwen", "revision": REVISION}}))
    proposer = build(FakeRuntime("invalid, never a rule fallback"))
    monkeypatch.setattr(models, "from_eval_config", lambda config: proposer)
    assert cli.main(["evaluate", "--config", str(config), "--out", str(tmp_path / "run"), "--offline"]) == 0
    assert json.loads(capsys.readouterr().out)["metrics"]["action_macro_f1"] == 0


def test_model_smoke_records_ten_development_requests(tmp_path, monkeypatch):
    from cam import cli, data
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    config = tmp_path / "base.json"
    config.write_text(json.dumps({"schema_version": 1, "data": {"manifest": str(generated / "manifest.json")},
                                  "proposer": {"kind": "qwen", "revision": REVISION}}))
    monkeypatch.setattr(models, "from_eval_config", lambda config: build(FakeRuntime("malformed")))
    out = tmp_path / "smoke"
    assert cli.main(["model-smoke", "--config", str(config), "--out", str(out), "--offline"]) == 0
    rows = [json.loads(line) for line in (out / "predictions.jsonl").read_text().splitlines()]
    assert len(rows) == 10
    assert all(row["raw_output"] == "malformed" for row in rows)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["model_status"] == "fake_runtime"
    assert manifest["backward_probe"]["weights_updated"] is False
    assert manifest["dataset"]["split"] == "pilot"
    assert manifest["peak_process_memory_bytes"] > 0


def test_model_smoke_rejects_holdout_before_loading_runtime(tmp_path, monkeypatch, capsys):
    from cam import cli
    config = tmp_path / "heldout.json"
    config.write_text(json.dumps({"schema_version": 1, "data": {"split": "test", "manifest": "unopened.json"},
                                  "proposer": {"kind": "qwen", "revision": REVISION}}))
    def forbidden(config):
        raise AssertionError("holdout smoke loaded model")
    monkeypatch.setattr(models, "from_eval_config", forbidden)
    assert cli.main(["model-smoke", "--config", str(config), "--out", str(tmp_path / "run")]) == 2
    assert "development" in capsys.readouterr().out


def test_device_transfer_failure_returns_unavailable_cli(tmp_path, monkeypatch, capsys):
    from cam import cli, data

    class FailingTensor:
        def to(self, device):
            raise RuntimeError("MPS allocation failed")

    runtime = models.HuggingFaceRuntime.__new__(models.HuggingFaceRuntime)
    runtime.device = "mps"
    runtime.metadata = {"backend": "mps", "dtype": "fake", "real_model": False}
    runtime.prepare = lambda messages: models.PreparedInput({"input_ids": FailingTensor()}, 4)
    proposer = models.ModelProposer(models.ModelConfig(revision=REVISION, device="mps"), runtime=runtime)
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=2), generated)
    config = tmp_path / "base.json"
    config.write_text(json.dumps({"schema_version": 1, "data": {"manifest": str(generated / "manifest.json")},
                                  "proposer": {"kind": "qwen", "revision": REVISION, "device": "mps"}}))
    monkeypatch.setattr(models, "from_eval_config", lambda config: proposer)
    assert cli.main(["evaluate", "--config", str(config), "--out", str(tmp_path / "run")]) == 3
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "unavailable"
    assert "MPS allocation failed" in response["error"]


@pytest.mark.parametrize("problem", ["base", "hash", "proof"])
def test_adapter_integrity_checked_before_runtime_load(tmp_path, problem):
    import hashlib
    checkpoint = tmp_path / "adapter"
    checkpoint.mkdir()
    (checkpoint / "adapter_config.json").write_text("{}")
    (checkpoint / "adapter_model.safetensors").write_bytes(b"unit-test-artifact")
    metadata = {"schema_version": 1, "status": "trained", "gate": "educational_imitation_only",
                "model": {"model_id": "Qwen/Qwen3-0.6B", "revision": REVISION, "tokenizer_revision": REVISION},
                "verification": {"base_unchanged": True, "adapter_changed": True, "reload_match": True},
                "adapter_files": {"adapter/" + p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.iterdir()}}
    if problem == "base":
        metadata["model"]["revision"] = "b" * 40
    elif problem == "hash":
        (checkpoint / "adapter_model.safetensors").write_bytes(b"tampered")
    else:
        metadata["verification"]["reload_match"] = False
    (tmp_path / "manifest.json").write_text(json.dumps(metadata))
    assert callable(getattr(models, "validate_adapter", None)), "adapter provenance validation is missing"
    with pytest.raises(c.ContractError, match="adapter"):
        models.validate_adapter(models.ModelConfig(revision=REVISION, adapter_path=str(checkpoint)))


def test_evaluator_records_verified_adapter_status(tmp_path):
    from cam import data, evaluate as evaluation
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=2), generated)
    runtime = FakeRuntime("raw invalid output")
    runtime.metadata = {**runtime.metadata, "adapter_status": "trained_educational"}
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run"), proposer=build(runtime))
    assert report.manifest["adapter_status"] == "trained_educational"


def test_smoke_records_verified_adapter_status(tmp_path, monkeypatch):
    from cam import data
    from cam.smoke import model_smoke
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    runtime = FakeRuntime("raw invalid output")
    runtime.metadata = {**runtime.metadata, "adapter_status": "trained_educational"}
    monkeypatch.setattr(models, "from_eval_config", lambda config: build(runtime))
    out = tmp_path / "smoke"
    model_smoke(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), out, proposer={"kind": "qwen"}))
    assert json.loads((out / "manifest.json").read_text())["adapter_status"] == "trained_educational"
