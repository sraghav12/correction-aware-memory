from dataclasses import asdict
import json

import pytest

from cam import data
from cam import contracts
from conftest import refresh_manifest


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


@pytest.mark.parametrize("failure", ["identity", "counts", "gold_join", "checkpoint_coverage", "duplicate_observation", "group_membership", "checkpoint_key", "future_knowledge"])
def test_dataset_integrity_rejects_false_correctness_evidence(tmp_path, failure):
    out = tmp_path / "data"
    data.generate_dataset(contracts.DataConfig(trajectories=3), out)
    manifest_path = out / "manifest.json"
    if failure in ("identity", "counts"):
        manifest = json.loads(manifest_path.read_text())
        if failure == "identity":
            manifest["dataset_id"] = "0" * 64
        else:
            manifest.update(trajectory_count=999, event_count=999)
        manifest_path.write_text(json.dumps(manifest))
    else:
        filename = {"gold_join": "gold.jsonl", "checkpoint_coverage": "checkpoints.jsonl", "duplicate_observation": "observations.jsonl", "group_membership": "groups.jsonl", "checkpoint_key": "checkpoints.jsonl", "future_knowledge": "checkpoints.jsonl"}[failure]
        rows = data.read_jsonl(out / filename)
        if failure == "gold_join": rows.pop()
        elif failure == "checkpoint_coverage": rows = rows[:1]
        elif failure == "duplicate_observation": rows.append(rows[0])
        elif failure == "group_membership": rows[0]["split"] = "test"
        elif failure == "checkpoint_key": rows[0]["entity_id"] = "wrong-entity"
        elif failure == "future_knowledge": rows[0]["known_at"] = "2027-01-01T00:00:00Z"
        data.write_jsonl(out / filename, rows)
        refresh_manifest(out)
    with pytest.raises(contracts.ContractError):
        data.read_dataset(manifest_path)
