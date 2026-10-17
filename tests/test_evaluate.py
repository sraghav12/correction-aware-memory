from dataclasses import asdict
import json

import pytest

from cam import evaluate as evaluation
from cam import contracts as c
from cam import data
from conftest import make_observation, make_proposal


def test_metric_denominators_on_known_errors():
    records = [{"kind": "state", "changed": True, "stale": i == 0, "missing": False, "exact": i != 0,
                "provenance_tp": 1, "provenance_claimed": 1, "provenance_expected": 1} for i in range(4)]
    records += [{"kind": "opportunity", "non_mutating": True, "semantic_changed": i == 0} for i in range(5)]
    metrics = evaluation._compute_metrics(records)
    assert metrics["stale_active_rate"] == {"numerator": 1, "denominator": 4, "value": 0.25}
    assert metrics["false_overwrite_rate"] == {"numerator": 1, "denominator": 5, "value": 0.2}


def test_zero_denominator_is_null():
    metrics = evaluation._compute_metrics([])
    assert metrics["stale_active_rate"] == {"numerator": 0, "denominator": 0, "value": None}


def test_always_no_op_has_missing_state(tmp_path):
    from cam.contracts import Proposal
    generated = tmp_path / "dataset"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    config = c.EvalConfig(data=c.DataConfig(manifest=generated / "manifest.json"), output_dir=tmp_path / "no-op")
    def no_op(request):
        o = request.observation
        return Proposal("no_op", None, None, None, o.source_id, o.evidence_start, o.evidence_end, "ambiguous", True)
    report = evaluation.evaluate(config, proposer=no_op)
    assert report.metrics["missing_state_rate"]["value"] == 1.0
    assert report.metrics["state_exact_match"]["value"] == 0.0


def test_rule_replay_matches_independent_oracle(tmp_path):
    generated = tmp_path / "dataset"
    data.generate_dataset(c.DataConfig(trajectories=8), generated)
    report = evaluation.evaluate(c.EvalConfig(data=c.DataConfig(manifest=generated / "manifest.json"), output_dir=tmp_path / "rule"))
    assert report.metrics["action_macro_f1"] == 1.0
    assert report.metrics["state_exact_match"]["value"] == 1.0
    assert report.metrics["stale_active_rate"]["value"] == 0.0
    assert report.metrics["invalid_output_rate"]["value"] == 0.0
    assert report.metrics["provenance_precision"]["value"] == 1.0
    assert report.metrics["invariant_violations"] == 0


def test_closed_loop_invalid_outputs_are_counted_and_preserved(tmp_path):
    from cam.policy import propose_rule
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    calls = 0
    def alternating(request):
        nonlocal calls
        calls += 1
        return propose_rule(request) if calls % 2 else "UNPARSEABLE ORIGINAL MODEL OUTPUT"
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run"), proposer=alternating)
    assert report.metrics["parse_invalid_rate_gold_history"]["value"] == 0.0
    assert report.metrics["parse_invalid_rate_closed_loop"]["value"] == 1.0
    assert report.metrics["invalid_output_rate"]["value"] == 0.5
    assert report.metrics["missing_state_rate"]["value"] == 1.0
    predictions = data.read_jsonl(report.run_dir / "predictions.jsonl")
    assert all(row["raw_output"] == "UNPARSEABLE ORIGINAL MODEL OUTPUT" for row in predictions if row["track"] == "closed_loop")


@pytest.mark.parametrize("historical", [False, True])
def test_false_overwrite_counts_changes_outside_current_time(tmp_path, monkeypatch, historical):
    # A deliberately controlled scoring fixture isolates timeline mutation from loader validation.
    # The real loader's full generated-format integrity is tested independently.
    from cam.policy import propose_rule
    from cam.contracts import Proposal
    first = make_observation()
    future = make_observation(oid="future", value="published", day=2, effective_day=10)
    conflict = make_observation(oid="conflict", value="withdrawn", day=3, effective_day=10)
    if historical:
        future = make_observation(oid="later", value="published", day=8, effective_day=7)
        conflict = make_observation(oid="correction", value="withdrawn", day=9, effective_day=1, corrects="o1", authorized=True)
    rows = [first, future, conflict]
    gold = [make_proposal(first), make_proposal(future, "supersede", "v:o1", "new_effective_state"), make_proposal(conflict, "no_op", reason="ambiguous", review=True)]
    fake_manifest = {"trajectory_count": 1, "split": "pilot", "review_status": "not_human_reviewed", "dataset_id": "scoring-unit-fixture"}
    dataset = {"observations.jsonl": rows, "gold.jsonl": [{"observation_id": o["observation_id"], "proposal": p} for o,p in zip(rows,gold)], "checkpoints.jsonl": []}
    monkeypatch.setattr(evaluation, "read_dataset", lambda path: (fake_manifest, dataset))
    calls = 0
    def divergent(request):
        nonlocal calls
        calls += 1
        if not historical and calls == 4:  # skip the future notice in closed-loop only
            o = request.observation
            return Proposal("no_op", None, None, None, o.source_id, o.evidence_start, o.evidence_end, "ambiguous", True)
        return propose_rule(request)
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=tmp_path / "controlled.json"), tmp_path / "run"), proposer=divergent)
    assert report.metrics["false_overwrite_rate"] == {"numerator": 1, "denominator": 1, "value": 1.0}
