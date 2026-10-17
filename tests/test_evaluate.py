from dataclasses import asdict
import json
from dataclasses import replace

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


def test_invalid_output_counts_as_error():
    rows = [{"kind": "proposal", "track": "gold_history", "expected_action": a,
             "predicted_action": a, "valid": True} for a in ("create", "reinforce", "supersede", "update", "no_op")]
    rows.append({"kind": "proposal", "track": "gold_history", "expected_action": "create", "valid": False})
    metrics = evaluation._compute_metrics(rows)
    assert metrics["action_classes"]["create"]["recall"] == 0.5
    assert metrics["action_macro_f1"] == pytest.approx(14 / 15)
    assert metrics["parse_invalid_rate_gold_history"]["denominator"] == 6


def test_raw_action_label_remains_visible_when_guard_rejects(tmp_path):
    from cam.policy import propose_rule
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    def forged(request):
        return replace(propose_rule(request), source_id="invented-source")
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run"), proposer=forged)
    assert report.metrics["action_macro_f1"] == 1.0
    assert report.metrics["guard_valid_action_macro_f1"] == 0.0
    assert report.metrics["validator_rejection_rate_gold_history"]["value"] == 1.0
    assert report.metrics["missing_state_rate"]["value"] == 1.0


def test_erroneous_mutations_among_all_commits_have_separate_denominator():
    rows = [{"kind": "opportunity", "non_mutating": True, "semantic_changed": True,
             "committed": True, "post_commit_exact": False}]
    rows += [{"kind": "opportunity", "non_mutating": False, "semantic_changed": True,
              "committed": True, "post_commit_exact": True} for _ in range(3)]
    rows.append({"kind": "opportunity", "non_mutating": True, "semantic_changed": False,
                 "committed": False, "post_commit_exact": False})
    metrics = evaluation._compute_metrics(rows)
    assert metrics["false_overwrite_rate"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert metrics["erroneous_mutations_among_commits"] == {"numerator": 1, "denominator": 4, "value": 0.25}


def test_bootstrap_resamples_whole_trajectory(monkeypatch):
    rows = [(10, 100, 0, 100), (1, 1, 0, 1)]
    class RecordedRandom:
        def __init__(self, seed):
            pass
        def choices(self, population, *, k):
            assert population == rows and k == 2
            return [population[0], population[0]]
    monkeypatch.setattr(evaluation, "random", type("RandomModule", (), {"Random": RecordedRandom}), raising=False)
    assert evaluation._paired_bootstrap(rows, seed=11, resamples=3) == (-0.1, -0.1)


def test_bootstrap_pools_counts_after_trajectory_resampling(monkeypatch):
    class RecordedRandom:
        def __init__(self, seed):
            pass
        def choices(self, population, *, k):
            return list(population)
    monkeypatch.setattr(evaluation, "random", type("RandomModule", (), {"Random": RecordedRandom}), raising=False)
    assert evaluation._paired_bootstrap([(10, 100, 0, 100), (1, 1, 0, 1)], seed=11, resamples=3) == pytest.approx((-11/101, -11/101))


def test_bootstrap_zero_denominators_remain_undefined():
    assert evaluation._paired_bootstrap([(0, 1, 0, 1)] * 2, seed=11) == (0.0, 0.0)
    result = evaluation._bootstrap_details([(0, 0, 0, 0)], seed=11, resamples=20)
    assert result["interval_95"] == [None, None]
    assert result["undefined_resamples"] == 20
    assert result["valid_resamples"] == 0


def comparison_fixture(tmp_path, **overrides):
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(split="development", trajectories=3), generated)
    arms = {}
    for name in ("base", "sft"):
        path = tmp_path / f"{name}.json"
        settings = {"schema_version": 1, "data": {"manifest": "data/manifest.json", "split": "development"},
                    "proposer": {"kind": "rule"}, "evaluation": {"seeds": [11], "qa_mode": "deterministic"}}
        settings.update(overrides.get(name, {}))
        path.write_text(json.dumps(settings))
        arms[name] = path.name
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps({"schema_version": 1, "purpose": "exploratory_development", "arms": arms,
                                "reference": "base", "seed": 11, "bootstrap_count": 20}))
    return path


@pytest.mark.parametrize("change", ["manifest", "generation", "model"])
def test_comparison_rejects_mismatched_manifest(tmp_path, change):
    from cam import compare as comparison
    path = comparison_fixture(tmp_path)
    sft = tmp_path / "sft.json"
    settings = json.loads(sft.read_text())
    if change == "manifest":
        data.generate_dataset(c.DataConfig(split="development", trajectories=3, seed=22), tmp_path / "other")
        settings["data"]["manifest"] = "other/manifest.json"
    elif change == "generation":
        settings["generation"] = {"max_new_tokens": 32}
    else:
        settings["proposer"] = {"kind": "qwen", "revision": "a" * 40, "device": "cpu"}
        base = json.loads((tmp_path / "base.json").read_text())
        base["proposer"] = {"kind": "qwen", "revision": "b" * 40, "device": "cpu"}
        (tmp_path / "base.json").write_text(json.dumps(base))
    sft.write_text(json.dumps(settings))
    with pytest.raises(c.ContractError, match="matched|identical"):
        comparison.compare(path, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_each_arm_has_independent_store(tmp_path):
    from cam import compare as comparison
    path = comparison_fixture(tmp_path)
    from cam.policy import propose_rule
    def invalid_factory(config):
        return lambda request: "invalid"
    result = comparison.compare(path, tmp_path / "run", proposer_factories={"sft": invalid_factory})
    assert result["arms"]["base"]["metrics"]["state_exact_match"]["value"] == 1.0
    assert result["arms"]["sft"]["metrics"]["missing_state_rate"]["value"] == 1.0
    assert result["training_seed_count"] == 0  # these test arms are rules, not training runs
    base = data.read_jsonl(tmp_path / "run/base/predictions.jsonl")
    sft = data.read_jsonl(tmp_path / "run/sft/predictions.jsonl")
    assert [r["request"] for r in base if r["track"] == "gold_history"] == [r["request"] for r in sft if r["track"] == "gold_history"]
    assert all(not r["request"]["candidate_versions"] for r in sft if r["track"] == "closed_loop")
    assert result["contrasts"]["sft"]["missing_state_rate"]["difference"] == 1.0


def test_unavailable_arm_is_not_scored_as_rule(tmp_path):
    from cam import compare as comparison
    def unavailable(config):
        raise c.RuntimeUnavailable("controlled backend unavailable")
    result = comparison.compare(comparison_fixture(tmp_path), tmp_path / "run", proposer_factories={"sft": unavailable})
    assert result["arms"]["sft"]["status"] == "unavailable"
    assert "metrics" not in result["arms"]["sft"]
    assert "sft" not in result["contrasts"]


def test_backend_failure_preserves_completed_calls_without_scores(tmp_path):
    from cam import compare as comparison
    from cam.policy import propose_rule
    def fails_after_one(config):
        calls = 0
        def proposer(request):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise c.RuntimeUnavailable("backend failed mid-run")
            return propose_rule(request)
        return proposer
    result = comparison.compare(comparison_fixture(tmp_path), tmp_path / "run", proposer_factories={"sft": fails_after_one})
    assert result["arms"]["sft"]["status"] == "unavailable"
    assert len(data.read_jsonl(tmp_path / "run/sft/predictions.jsonl")) == 1
    assert not (tmp_path / "run/sft/metrics.json").exists()


def test_latest_arrival_diagnostic_retains_shared_guard(tmp_path):
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run",
                                             proposer={"kind": "latest_arrival"}))
    assert report.metrics["guard_rejections"] > 0
    assert report.metrics["mechanical_provenance_validity"]["value"] == 1.0
    assert report.metrics["state_exact_match"]["value"] < 1.0
    assert report.manifest["model_status"] == "diagnostic"


def test_comparison_cli_creates_replayable_reports(tmp_path, capsys):
    from cam import cli
    config = comparison_fixture(tmp_path)
    out = tmp_path / "run"
    assert cli.main(["compare", "--config", str(config), "--out", str(out), "--offline"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == "ok"
    result = json.loads((out / "comparison.json").read_text())
    assert result["contrasts"]["sft"]["stale_active_rate"]["interval_95"] == [0.0, 0.0]
    assert (out / "registration.json").exists()
    assert (out / "index.html").exists()
    assert (out / "comparison.md").exists()


def test_seed_variation_not_pooled_as_events(tmp_path):
    from cam import compare as comparison
    path = comparison_fixture(tmp_path, sft={"evaluation": {"seeds": [11, 22], "qa_mode": "deterministic"}})
    with pytest.raises(c.ContractError, match="seed"):
        comparison.compare(path, tmp_path / "run")


def test_comparison_requires_data_and_matching_declared_seed(tmp_path):
    from cam import compare as comparison
    path = comparison_fixture(tmp_path)
    arm = tmp_path / "sft.json"
    settings = json.loads(arm.read_text())
    settings["data"]["seed"] = 22
    arm.write_text(json.dumps(settings))
    with pytest.raises(c.ContractError, match="seed"):
        comparison.compare(path, tmp_path / "run")
    settings["data"].pop("manifest")
    arm.write_text(json.dumps(settings))
    with pytest.raises(c.ContractError, match="manifest"):
        comparison.compare(path, tmp_path / "run")


def test_recovery_action_is_not_scored_against_wrong_context(tmp_path):
    from cam.policy import propose_rule
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    # Skip initial creates only in the closed-loop pass. Subsequent recovery
    # creates must not be compared with gold-history reinforce labels.
    calls = 0
    skipped = set()
    def divergent(request):
        nonlocal calls
        calls += 1
        if calls % 2 == 0 and request.observation.trajectory_id not in skipped:
            skipped.add(request.observation.trajectory_id)
            return "missing initial output"
        return propose_rule(request)
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run"), proposer=divergent)
    rows = data.read_jsonl(report.run_dir / "predictions.jsonl")
    gold = {r["observation_id"]: r for r in rows if r["track"] == "gold_history"}
    recoveries = [r for r in rows if r["track"] == "closed_loop" and r["proposal"] and r["proposal"]["action"] == "create" and gold[r["observation_id"]]["proposal"]["action"] == "reinforce"]
    assert recoveries
    assert report.metrics["action_macro_f1"] == 1.0
    assert report.metrics["resources"]["tracks"]["gold_history"]["proposer_calls"] == len(rows) // 2


def test_qa_cannot_see_future(tmp_path):
    generated = tmp_path / "data"
    data.generate_dataset(c.DataConfig(trajectories=3), generated)
    report = evaluation.evaluate(c.EvalConfig(c.DataConfig(manifest=generated / "manifest.json"), tmp_path / "run"))
    observations = data.read_jsonl(generated / "observations.jsonl")
    known = {r["source_id"]: r["observed_at"] for r in observations}
    checkpoints = data.read_jsonl(report.run_dir / "checkpoints.jsonl")
    assert all(known[source] <= row["known_at"] for row in checkpoints for source in row["selected"]["source_ids"])
    assert report.metrics["deterministic_qa_exact_match"]["value"] == 1.0
