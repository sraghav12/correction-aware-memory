"""Separate one-step proposal scoring and closed-loop state evaluation."""

from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import time

from cam.contracts import ContractError, EvalConfig, EvalReport, canonical_json, parse_observation, parse_proposal
from cam.data import prepare_output, read_dataset, write_json, write_jsonl
from cam.policy import propose_rule, validate
from cam.store import Store


class CorrectnessError(RuntimeError):
    """An independent oracle or program invariant failed."""


def _rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None}


def _compute_metrics(records: list[dict]) -> dict:
    states = [r for r in records if r["kind"] == "state"]
    opportunities = [r for r in records if r["kind"] == "opportunity"]
    all_proposals = [r for r in records if r["kind"] == "proposal"]
    proposals = [r for r in all_proposals if r.get("track", "gold_history") == "gold_history"]
    per_class = {}
    for action in ("create", "reinforce", "supersede", "update", "no_op"):
        tp = sum(r["expected_action"] == r.get("predicted_action") == action for r in proposals)
        support = sum(r["expected_action"] == action for r in proposals)
        predicted = sum(r.get("predicted_action") == action for r in proposals)
        precision, recall = tp / predicted if predicted else 0.0, tp / support if support else 0.0
        per_class[action] = {"support": support, "predicted": predicted, "precision": precision, "recall": recall,
                             "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    result = {
        "action_macro_f1": sum(row["f1"] for row in per_class.values()) / 5,
        "action_classes": per_class,
        "stale_active_rate": _rate(sum(r.get("stale", False) for r in states if r["changed"]), sum(r["changed"] for r in states)),
        "missing_state_rate": _rate(sum(r["missing"] for r in states), len(states)),
        "state_exact_match": _rate(sum(r["exact"] for r in states), len(states)),
        "false_overwrite_rate": _rate(sum(r["non_mutating"] and r["semantic_changed"] for r in opportunities), sum(r["non_mutating"] for r in opportunities)),
        "invalid_output_rate": _rate(sum(not r.get("valid", True) for r in all_proposals), len(all_proposals)),
        "provenance_precision": _rate(sum(r["provenance_tp"] for r in states), sum(r["provenance_claimed"] for r in states)),
        "provenance_recall": _rate(sum(r["provenance_tp"] for r in states), sum(r["provenance_expected"] for r in states)),
    }
    for track in ("gold_history", "closed_loop"):
        subset = [r for r in all_proposals if r.get("track", "gold_history") == track]
        parsed = [r for r in subset if r.get("valid", True)]
        result[f"parse_invalid_rate_{track}"] = _rate(sum(not r.get("valid", True) for r in subset), len(subset))
        result[f"validator_rejection_rate_{track}"] = _rate(sum(r.get("validator_rejected", False) for r in parsed), len(parsed))
    for kind in ("current", "historical_or_future"):
        subset = [r for r in states if r.get("query_kind") == kind]
        result[f"state_exact_match_{kind}"] = _rate(sum(r["exact"] for r in subset), len(subset))
    result["deterministic_qa_exact_match"] = _rate(sum(r["exact"] and r["provenance_tp"] == r["provenance_expected"] == r["provenance_claimed"] for r in states), len(states))
    return result


def _semantic(view):
    return view.status, view.value, view.effective_at


def _predict(proposer, request):
    started = time.perf_counter()
    raw = None
    try:
        raw = proposer(request)
        if is_dataclass(raw):
            raw = asdict(raw)
        payload = json.loads(raw) if isinstance(raw, str) else raw
        proposal = parse_proposal(payload)
        return proposal, None, time.perf_counter() - started, raw
    except (ContractError, TypeError, ValueError) as error:
        # Preserve the original returned payload, including malformed model text.
        raw = getattr(error, "raw_output", raw)
        try:
            canonical_json(raw)
        except TypeError:
            raw = {"unserializable_type": type(raw).__name__, "representation": repr(raw)}
        return None, str(error), time.perf_counter() - started, raw


def model_identity(proposer):
    metadata = getattr(proposer, "metadata", None)
    if metadata is not None:
        return ("evaluated" if metadata.get("real_model") else "fake_runtime"), metadata
    return ("not_run" if proposer is propose_rule else "custom_callable"), {}


def run_environment():
    project = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=project, text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = None, None
    return {"git_commit": commit, "git_dirty": dirty,
            "dependency_lock_sha256": hashlib.sha256((project / "uv.lock").read_bytes()).hexdigest(),
            "python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine()}


def evaluate(config: EvalConfig, *, proposer=None) -> EvalReport:
    if proposer is None and config.proposer.get("kind", "rule") != "rule":
        from cam.models import from_eval_config
        proposer = from_eval_config(config)
    if config.data.manifest is None:
        raise ContractError("data.manifest is required for evaluation")
    manifest, dataset = read_dataset(config.data.manifest)
    if config.data.split != manifest["split"]:
        raise ContractError("configured split differs from dataset manifest")
    if proposer is None:
        proposer = propose_rule
    model_status, runtime = model_identity(proposer)
    prepare_output(config.output_dir)
    gold = {row["observation_id"]: row for row in dataset["gold.jsonl"]}
    checkpoints = defaultdict(list)
    for row in dataset["checkpoints.jsonl"]:
        checkpoints[row["observation_id"]].append(row)
    records, predictions, saved_checkpoints, latencies = [], [], [], []
    guard_rejections, mechanical_valid, mechanical_total = 0, 0, 0
    started = time.perf_counter()
    with Store(config.output_dir / "gold-history.sqlite") as reference, Store(config.output_dir / "memory.sqlite") as memory:
        for raw in dataset["observations.jsonl"]:
            observation = parse_observation(raw)
            expected_proposal = parse_proposal(gold[observation.observation_id]["proposal"])
            request = reference.snapshot(observation)
            one_step, parse_error, latency, raw_output = _predict(proposer, request)
            one_step_codes = validate(request, one_step) if one_step else []
            latencies.append(latency)
            records.append({"kind": "proposal", "track": "gold_history", "trajectory_id": observation.trajectory_id,
                            "expected_action": expected_proposal.action, "predicted_action": one_step.action if one_step and not one_step_codes else None,
                            "valid": one_step is not None, "validator_rejected": bool(one_step_codes)})
            predictions.append({"track": "gold_history", "observation_id": observation.observation_id,
                                "trajectory_id": observation.trajectory_id, "request": asdict(request),
                                "proposal": asdict(one_step) if one_step else None, "raw_output": raw_output,
                                "validation_codes": one_step_codes, "parse_error": parse_error, "latency_seconds": latency,
                                "model_call": dict(getattr(proposer, "last_metadata", {}))})
            accepted = reference.commit(request, expected_proposal)
            if accepted.status != "committed":
                raise CorrectnessError(f"independent gold proposal rejected: {observation.observation_id}: {accepted.validation_codes}")
            live_request = memory.snapshot(observation)
            # Check every possibly affected boundary, including future and historical facts.
            boundaries = {version.effective_at for version in live_request.candidate_versions}
            if observation.effective_at is not None:
                boundaries.add(observation.effective_at)
            def semantic_timeline():
                return tuple((boundary, _semantic(memory.view(observation.entity_id, observation.predicate,
                             effective_as_of=boundary, known_at=observation.observed_at))) for boundary in sorted(boundaries))
            before = semantic_timeline()
            closed_loop, parse_error, latency, raw_output = _predict(proposer, live_request)
            latencies.append(latency)
            committed = memory.commit(live_request, closed_loop) if closed_loop else None
            guard_rejections += int(committed is not None and committed.status == "rejected")
            mechanical_total += 1
            mechanical_valid += int(closed_loop is not None and "EVIDENCE_MISMATCH" not in (committed.validation_codes if committed else ()))
            records.append({"kind": "proposal", "track": "closed_loop", "trajectory_id": observation.trajectory_id,
                            "valid": closed_loop is not None, "validator_rejected": committed is not None and committed.status == "rejected"})
            predictions.append({"track": "closed_loop", "observation_id": observation.observation_id,
                                "trajectory_id": observation.trajectory_id, "request": asdict(live_request),
                                "proposal": asdict(closed_loop) if closed_loop else None, "raw_output": raw_output, "parse_error": parse_error,
                                "commit": asdict(committed) if committed else None, "latency_seconds": latency,
                                "model_call": dict(getattr(proposer, "last_metadata", {}))})
            after = semantic_timeline()
            records.append({"kind": "opportunity", "trajectory_id": observation.trajectory_id,
                            "non_mutating": expected_proposal.action in ("no_op", "reinforce"),
                            "semantic_changed": before != after})
            for checkpoint in checkpoints[observation.observation_id]:
                selected = memory.view(observation.entity_id, observation.predicate, effective_as_of=checkpoint["effective_as_of"], known_at=checkpoint["known_at"])
                expected = checkpoint["expected"]
                exact = all(getattr(selected, key) == expected[key] for key in ("value", "status", "effective_at", "effective_until"))
                actual_sources, expected_sources = set(selected.source_ids), set(expected["source_ids"])
                record = {"kind": "state", "trajectory_id": observation.trajectory_id,
                          "query_kind": checkpoint["query_kind"], "changed": checkpoint["changed"],
                          "stale": selected.status != "absent" and selected.value in checkpoint["obsolete_values"],
                          "missing": selected.status == "absent" and expected["status"] != "absent", "exact": exact,
                          "provenance_tp": len(actual_sources & expected_sources), "provenance_claimed": len(actual_sources),
                          "provenance_expected": len(expected_sources)}
                records.append(record)
                saved_checkpoints.append({**checkpoint, "selected": asdict(selected), "score": record})
    metrics = _compute_metrics(records)
    metrics.update(observation_count=len(dataset["observations.jsonl"]), trajectory_count=manifest["trajectory_count"],
                   checkpoint_count=len(saved_checkpoints), invariant_violations=0, guard_rejections=guard_rejections,
                   mechanical_provenance_validity=_rate(mechanical_valid, mechanical_total))
    metrics["correctness_gate_passed"] = metrics["state_exact_match"]["value"] == 1 and metrics["action_macro_f1"] == 1 and guard_rejections == 0
    metrics["resources"] = {"wall_seconds": time.perf_counter() - started, "proposer_calls": len(latencies),
                            "proposer_p50_seconds": statistics.median(latencies),
                            "proposer_p95_seconds": sorted(latencies)[max(0, int(len(latencies) * .95) - 1)],
                            "peak_process_memory_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024),
                            "backend": runtime.get("backend", "python-rules" if proposer is propose_rule else "custom-callable"),
                            "model_runtime_evaluated": runtime.get("real_model", False),
                            "tokens": {key: sum(row["model_call"].get(key, 0) for row in predictions)
                                       for key in ("input_tokens", "output_tokens")} if runtime else None}
    per_trajectory = {tid: _compute_metrics([r for r in records if r.get("trajectory_id") == tid]) for tid in sorted({r["trajectory_id"] for r in records})}
    resolved = json.loads(canonical_json(config))
    run_manifest = {"schema_version": 1, "dataset": manifest, **run_environment(), "model": runtime,
                    "review_status": manifest["review_status"], "model_status": model_status,
                    "adapter_status": "not_trained", "tracks": ["gold_history", "closed_loop"]}
    write_json(config.output_dir / "resolved-config.json", resolved)
    write_json(config.output_dir / "manifest.json", run_manifest)
    write_json(config.output_dir / "metrics.json", metrics)
    write_json(config.output_dir / "per-trajectory.json", per_trajectory)
    write_jsonl(config.output_dir / "predictions.jsonl", predictions)
    write_jsonl(config.output_dir / "checkpoints.jsonl", saved_checkpoints)
    observations_by_id = {row["observation_id"]: row for row in dataset["observations.jsonl"]}
    sample = []
    for action in ("create", "reinforce", "supersede", "update", "no_op"):
        sample.extend([row for row in dataset["gold.jsonl"] if row["proposal"]["action"] == action][:10])
    selected_ids = {row["observation_id"] for row in sample}
    sample.extend(row for row in dataset["gold.jsonl"] if row["observation_id"] not in selected_ids)
    sample = sample[:50]
    audit = [{"observation": observations_by_id[row["observation_id"]], "expected_proposal": row["proposal"],
              "expected_checkpoints": checkpoints[row["observation_id"]], "human_reviewer": None, "human_verdict": None} for row in sample]
    write_jsonl(config.output_dir / "label-audit.jsonl", audit)
    audit_lines = ["# Pilot label audit", "", "Status: not human reviewed. Review these expected actions and states against source evidence; record actual reviewer, date, disagreements and adjudication. This is development data forever.", "", "| Observation | Expected action | Evidence | Human verdict |", "|---|---|---|---|"]
    for row in audit:
        observation = row["observation"]
        evidence = observation["text"].replace("|", "\\|").replace("\n", " ")
        audit_lines.append(f"| {observation['observation_id']} | {row['expected_proposal']['action']} | {evidence} | pending |")
    (config.output_dir / "label-audit.md").write_text("\n".join(audit_lines) + "\n")
    return EvalReport(config.output_dir, metrics, run_manifest)
