from dataclasses import asdict
import json

import pytest

from cam import evaluate as evaluation
from cam import contracts as c
from cam import data


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
