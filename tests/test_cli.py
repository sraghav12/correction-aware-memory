import json
import hashlib
from pathlib import Path
import socket
import sys

import pytest

from cam import cli


def write_config(path, manifest):
    path.write_text(json.dumps({"schema_version": 1, "data": {"manifest": str(manifest), "split": "pilot", "seed": 11, "trajectories": 5}, "proposer": {"kind": "rule"}, "generation": {}, "training": {}, "evaluation": {}}))


def test_offline_end_to_end_without_ml(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "socket", forbidden)
    config = tmp_path / "offline.json"
    generated, run = tmp_path / "generated", tmp_path / "run"
    write_config(config, generated / "manifest.json")
    assert cli.main(["generate", "--config", str(config), "--out", str(generated), "--offline"]) == 0
    assert cli.main(["evaluate", "--config", str(config), "--out", str(run), "--offline"]) == 0
    assert cli.main(["report", "--run", str(run), "--out", str(run / "report"), "--offline"]) == 0
    assert (run / "report/index.html").is_file()
    assert not ({"torch", "transformers", "peft", "trl"} & sys.modules.keys())
    assert all(json.loads(line) for line in capsys.readouterr().out.splitlines())


def test_report_matches_run_counts(tmp_path):
    config = tmp_path / "offline.json"
    generated, run = tmp_path / "generated", tmp_path / "run"
    write_config(config, generated / "manifest.json")
    cli.main(["generate", "--config", str(config), "--out", str(generated), "--offline"])
    cli.main(["evaluate", "--config", str(config), "--out", str(run), "--offline"])
    cli.main(["report", "--run", str(run), "--out", str(run / "report"), "--offline"])
    metrics = json.loads((run / "metrics.json").read_text())
    html = (run / "report/index.html").read_text()
    assert str(metrics["observation_count"]) in html
    assert "not_human_reviewed" in html
    assert "adapter" in html.lower()


def test_cli_exit_codes_and_strict_config(tmp_path):
    invalid = tmp_path / "bad.json"
    invalid.write_text('{"schema_version": 1, "data": {}, "unexpected": true}')
    assert cli.main(["generate", "--config", str(invalid), "--out", str(tmp_path / "bad"), "--offline"]) == 2
    write_config(invalid, tmp_path / "missing/manifest.json")
    assert cli.main(["evaluate", "--config", str(invalid), "--out", str(tmp_path / "bad"), "--offline"]) == 2


def test_optional_model_and_training_are_explicitly_unavailable(tmp_path, capsys):
    config = tmp_path / "model.json"
    write_config(config, tmp_path / "missing/manifest.json")
    raw = json.loads(config.read_text())
    raw["proposer"] = {"kind": "qwen", "model_id": "Qwen/Qwen3-0.6B", "revision": "a" * 40}
    config.write_text(json.dumps(raw))
    assert cli.main(["evaluate", "--config", str(config), "--out", str(tmp_path / "model"), "--offline"]) == 3
    assert cli.main(["train", "--config", str(config), "--out", str(tmp_path / "adapter"), "--offline"]) == 3
    assert "unavailable" in capsys.readouterr().out
    assert not (tmp_path / "model").exists()
    assert not (tmp_path / "adapter").exists()


def test_cli_correctness_failure_exit_code(tmp_path):
    from cam.data import generate_dataset
    from cam.contracts import DataConfig
    generated = tmp_path / "generated"
    generate_dataset(DataConfig(trajectories=1), generated)
    gold = [json.loads(line) for line in (generated / "gold.jsonl").read_text().splitlines()]
    gold[0]["proposal"]["value"] = "withdrawn"  # conflicts with the observed preliminary claim
    (generated / "gold.jsonl").write_text("".join(json.dumps(row) + "\n" for row in gold))
    manifest = json.loads((generated / "manifest.json").read_text())
    manifest["files"]["gold.jsonl"] = hashlib.sha256((generated / "gold.jsonl").read_bytes()).hexdigest()
    (generated / "manifest.json").write_text(json.dumps(manifest))
    config = tmp_path / "config.json"
    write_config(config, generated / "manifest.json")
    assert cli.main(["evaluate", "--config", str(config), "--out", str(tmp_path / "bad-run"), "--offline"]) == 4


def test_report_escapes_untrusted_text(tmp_path):
    config = tmp_path / "offline.json"
    generated, run = tmp_path / "generated", tmp_path / "run"
    write_config(config, generated / "manifest.json")
    cli.main(["generate", "--config", str(config), "--out", str(generated), "--offline"])
    cli.main(["evaluate", "--config", str(config), "--out", str(run), "--offline"])
    path = run / "predictions.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        row["request"]["observation"]["text"] = '<script>alert("injection")</script>'
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert cli.main(["report", "--run", str(run), "--out", str(run / "report"), "--offline"]) == 0
    html = (run / "report/index.html").read_text()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_output_directory_boundary(tmp_path):
    config = tmp_path / "config.json"
    write_config(config, tmp_path / "data/manifest.json")
    target = tmp_path / "output"
    target.mkdir()
    keep = target / "existing-user-file.txt"
    keep.write_text("keep me")
    before = set(tmp_path.rglob("*"))
    assert cli.main(["generate", "--config", str(config), "--out", str(target), "--offline"]) == 2
    assert set(tmp_path.rglob("*")) == before
    assert keep.read_text() == "keep me"
