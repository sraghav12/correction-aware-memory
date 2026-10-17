from dataclasses import asdict
import json

import pytest

from cam import data
from cam import contracts


def test_seed_reproduces_manifest(tmp_path):
    config = contracts.DataConfig(seed=11, trajectories=50)
    first = data.generate_dataset(config, tmp_path / "first")
    second = data.generate_dataset(config, tmp_path / "second")
    assert asdict(first) == asdict(second)
    assert (tmp_path / "first/observations.jsonl").read_bytes() == (tmp_path / "second/observations.jsonl").read_bytes()


def test_split_and_prompt_leakage(tmp_path):
    groups = {}
    texts = {}
    for split in ("train", "development", "test", "style_transfer"):
        out = tmp_path / split
        data.generate_dataset(contracts.DataConfig(seed=11, trajectories=5, split=split), out)
        groups[split] = {row["template_family"] for row in data.read_jsonl(out / "groups.jsonl")}
        observations = data.read_jsonl(out / "observations.jsonl")
        texts[split] = {o["text"] for o in observations}
        assert all("gold_action" not in o and "event_kind" not in o for o in observations)
    assert groups["train"].isdisjoint(groups["test"] | groups["style_transfer"])
    assert texts["train"].isdisjoint(texts["test"])


def test_reference_oracle_is_not_policy_call(tmp_path, monkeypatch):
    from cam import policy
    from cam.store import Store
    def forbidden(*args, **kwargs):
        raise AssertionError("production policy/store used to generate expected state")
    monkeypatch.setattr(policy, "propose_rule", forbidden)
    monkeypatch.setattr(policy, "validate", forbidden)
    monkeypatch.setattr(Store, "view", forbidden)
    data.generate_dataset(contracts.DataConfig(trajectories=5), tmp_path / "independent")


def test_all_actions_and_stale_cases_present(tmp_path):
    out = tmp_path / "pilot"
    manifest = data.generate_dataset(contracts.DataConfig(), out)
    gold = data.read_jsonl(out / "gold.jsonl")
    assert manifest.trajectory_count == 50
    assert 300 <= manifest.event_count <= 500
    assert {r["proposal"]["action"] for r in gold} == {"create", "reinforce", "supersede", "update", "no_op"}
    assert any(r["proposal"]["reason_code"] == "stale" for r in gold)
    assert manifest.review_status == "not_human_reviewed"


def test_manifest_tamper_and_output_overwrite_rejected(tmp_path):
    out = tmp_path / "data"
    data.generate_dataset(contracts.DataConfig(trajectories=2), out)
    (out / "observations.jsonl").write_text("tampered\n")
    with pytest.raises(contracts.ContractError, match="hash"):
        data.read_dataset(out / "manifest.json")
    with pytest.raises(contracts.ContractError, match="empty"):
        data.generate_dataset(contracts.DataConfig(), out)
