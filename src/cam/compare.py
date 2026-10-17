"""Prospectively registered, matched exploratory development comparisons."""

import gc
import hashlib
import json
from pathlib import Path
import re

from cam.contracts import ContractError, GenerationConfig, ModelConfig, RuntimeUnavailable, canonical_json, digest, load_config
from cam.data import prepare_output, read_dataset, read_jsonl, write_json
from cam.evaluate import CorrectnessError, _bootstrap_details, evaluate, run_environment
from cam.prompts import SYSTEM
from cam.report import write_comparison_report, write_report


def compare(config_path: Path, output_dir: Path, *, proposer_factories=None):
    raw = json.loads(config_path.read_text())
    keys = {"schema_version", "purpose", "arms", "reference", "seed", "bootstrap_count"}
    if not isinstance(raw, dict) or set(raw) != keys or type(raw["schema_version"]) is not int or raw["schema_version"] != 1 or raw["purpose"] != "exploratory_development":
        raise ContractError("invalid exploratory comparison config")
    if (not isinstance(raw["arms"], dict) or not 2 <= len(raw["arms"]) <= 8
            or any(not re.fullmatch(r"[a-z][a-z0-9-]{0,40}", name) or not isinstance(path, str) for name, path in raw["arms"].items())
            or raw["reference"] not in raw["arms"] or type(raw["seed"]) is not int):
        raise ContractError("comparison requires named arms, a reference and an integer seed")
    # Validate the statistics budget and all configs/data before preparing output or loading models.
    _bootstrap_details([(0, 1, 0, 1)], seed=raw["seed"], resamples=raw["bootstrap_count"])
    configs, manifests, model_pins, training_seeds, adapter_notes = {}, {}, set(), set(), []
    for name, path in raw["arms"].items():
        config = load_config((config_path.parent / path).resolve(), output_dir / name)
        if config.data.split not in ("pilot", "development"):
            raise ContractError("exploratory comparison never opens final test/train/style data")
        if config.data.manifest is None:
            raise ContractError("comparison data.manifest is required")
        if config.evaluation.get("seeds", [raw["seed"]]) != [raw["seed"]]:
            raise ContractError("one inference seed per comparison; report training seed variation separately, never pool events")
        if config.evaluation.get("qa_mode", "deterministic") != "deterministic":
            raise ContractError("only deterministic QA is supported")
        if config.evaluation.get("bootstrap_count", raw["bootstrap_count"]) != raw["bootstrap_count"]:
            raise ContractError("matched bootstrap settings must be identical")
        manifests[name], _ = read_dataset(config.data.manifest)
        if manifests[name]["split"] != config.data.split:
            raise ContractError("matched split differs from manifest")
        if manifests[name]["seed"] != config.data.seed:
            raise ContractError("declared data seed differs from matched manifest seed")
        if config.proposer["kind"] == "qwen":
            model = ModelConfig(**{key: value for key, value in config.proposer.items() if key != "kind"})
            model_pins.add((model.model_id, model.revision, model.device))
            if model.adapter_path:
                from cam.models import validate_adapter
                validate_adapter(model)
                training = json.loads((Path(model.adapter_path).parent / "manifest.json").read_text())
                training_seeds.add(training["seed"])
                if training.get("overfit_achieved") is False:
                    adapter_notes.append(f"overfit acceptance not achieved by configured adapter: {name}")
                if training.get("development_dataset", {}).get("dataset_id") == manifests[name]["dataset_id"]:
                    adapter_notes.append(f"configured adapter {name}: reload probes used this development dataset")
        configs[name] = config
    identities = {digest(m) for m in manifests.values()}
    budgets = {canonical_json(GenerationConfig(**c.generation)) for c in configs.values()}
    if len(identities) != 1 or len(budgets) != 1 or len(model_pins) > 1:
        raise ContractError("matched arms require identical manifests, generation budgets and model/tokenizer/backend pins")
    prepare_output(output_dir)
    registration = {**raw, "resolved_arms": {name: json.loads(canonical_json(c)) for name, c in configs.items()},
        "dataset": next(iter(manifests.values())), **run_environment(), "prompt_system_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "primary": "pooled stale_active_rate arm-minus-reference; negative favors arm only with missing/false-overwrite non-regression",
        "constraints": ["missing_state_rate", "false_overwrite_rate"], "warmup": "none; first calls retained",
        "reviewers": 0, "training_seed_variation": ("not applicable; no configured adapters" if not training_seeds
                         else "not estimable from one training seed" if len(training_seeds) == 1
                         else "not estimated; training seeds remain separate arm metadata"), "final_test_accessed": False,
        "limitations": ["exploratory synthetic annotated development data", *adapter_notes, "no human label review",
                        "no final generalization or research-superiority claim", "intervals conditional on this tiny development sample",
                        "equal-token/no-correction research controls and guard-removal sandbox deferred; unconstrained decoding only"]}
    write_json(output_dir / "registration.json", registration)
    arms, golden_requests = {}, None
    for name, config in configs.items():
        print(f"comparison arm {name}: starting", flush=True)
        proposer = None
        try:
            if proposer_factories and name in proposer_factories:
                proposer = proposer_factories[name](config)
            report = evaluate(config, proposer=proposer)
        except RuntimeUnavailable as error:
            arms[name] = {"status": "unavailable", "error": str(error), "scored": False}
            config.output_dir.mkdir(exist_ok=True)
            write_json(config.output_dir / "unavailable.json", arms[name])
            print(f"comparison arm {name}: unavailable: {error}", flush=True)
            continue
        finally:
            proposer = None
            gc.collect()
        requests = [row["request"] for row in read_jsonl(report.run_dir / "predictions.jsonl") if row["track"] == "gold_history"]
        if golden_requests is not None and requests != golden_requests:
            raise CorrectnessError("matched gold-history requests diverged across arms")
        golden_requests = requests
        per_trajectory = json.loads((report.run_dir / "per-trajectory.json").read_text())
        arms[name] = {"status": "evaluated", "metrics": report.metrics, "manifest": report.manifest,
                      "per_trajectory": per_trajectory, "diagnostic": config.proposer["kind"] == "latest_arrival"}
        write_report(report, report.run_dir / "report")
        print(f"comparison arm {name}: complete", flush=True)
    contrasts = {}
    reference = arms[raw["reference"]]
    if reference["status"] == "evaluated":
        for name, arm in arms.items():
            if name == raw["reference"] or arm["status"] != "evaluated":
                continue
            base, other = reference["per_trajectory"], arm["per_trajectory"]
            if set(base) != set(other):
                raise CorrectnessError("paired trajectory identities differ")
            contrasts[name] = {}
            for metric, rate in reference["metrics"].items():
                if not isinstance(rate, dict) or "denominator" not in rate:
                    continue
                pairs = [(base[tid][metric]["numerator"], base[tid][metric]["denominator"],
                          other[tid][metric]["numerator"], other[tid][metric]["denominator"]) for tid in sorted(base)]
                contrasts[name][metric] = _bootstrap_details(pairs, seed=raw["seed"], resamples=raw["bootstrap_count"])
    result = {"schema_version": 1, "purpose": raw["purpose"], "reference": raw["reference"], "registration_sha256": digest(registration),
              "arms": arms, "contrasts": contrasts, "inference_seed": raw["seed"], "inference_seed_count": 1,
              "training_seed_count": len(training_seeds), "training_seeds": sorted(training_seeds),
              "seed_variation": None, "final_test_accessed": False, "limitations": registration["limitations"]}
    write_json(output_dir / "comparison.json", result)
    write_comparison_report(result, output_dir)
    return result
