"""Ten gold-history development requests and a tiny backward compatibility probe."""

from dataclasses import asdict
import json
import platform
import resource
import time

from cam.contracts import ContractError, canonical_json, parse_observation, parse_proposal
from cam.data import prepare_output, read_dataset, write_json, write_jsonl
from cam.evaluate import CorrectnessError, _predict, model_identity, run_environment
from cam.policy import validate
from cam.store import Store


def model_smoke(config):
    if config.proposer.get("kind") != "qwen" or config.data.split not in ("pilot", "development"):
        raise ContractError("model-smoke requires a qwen proposer and pilot/development data; holdout is never opened")
    if config.data.manifest is None:
        raise ContractError("data.manifest is required")
    manifest, dataset = read_dataset(config.data.manifest)
    if manifest["split"] != config.data.split or len(dataset["observations.jsonl"]) < 10:
        raise ContractError("development smoke requires a matching split and at least ten observations")
    from cam.models import from_eval_config
    proposer = from_eval_config(config)
    prepare_output(config.output_dir)
    gold = {row["observation_id"]: row["proposal"] for row in dataset["gold.jsonl"]}
    rows, started = [], time.perf_counter()
    with Store(config.output_dir / "gold-history.sqlite") as reference:
        for raw in dataset["observations.jsonl"][:10]:
            observation = parse_observation(raw)
            request = reference.snapshot(observation)
            proposal, error, latency, raw_output = _predict(proposer, request)
            rows.append({"observation_id": observation.observation_id, "request": asdict(request),
                         "proposal": asdict(proposal) if proposal else None, "raw_output": raw_output,
                         "parse_error": error, "validation_codes": validate(request, proposal) if proposal else [],
                         "latency_seconds": latency, "model_call": dict(proposer.last_metadata)})
            result = reference.commit(request, parse_proposal(gold[observation.observation_id]))
            if result.status != "committed":
                raise CorrectnessError("gold-history development fixture failed commit validation")
    # Save inference diagnostics before the optional backward path, including failures.
    write_jsonl(config.output_dir / "predictions.jsonl", rows)
    status, runtime = model_identity(proposer)
    run = {"schema_version": 1, "purpose": "development_runtime_probe", "dataset": manifest,
           **run_environment(), "model_status": status, "model": runtime, "adapter_status": runtime.get("adapter_status", "not_trained"),
           "review_status": manifest["review_status"], "requests": len(rows),
           "backward_probe": proposer.runtime.probe_backward(), "wall_seconds": time.perf_counter() - started,
           "peak_process_memory_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)}
    write_json(config.output_dir / "manifest.json", run)
    write_json(config.output_dir / "resolved-config.json", json.loads(canonical_json(config)))
    return {"run": str(config.output_dir), "model_status": status, "requests": len(rows), "backward_probe": run["backward_probe"]}
