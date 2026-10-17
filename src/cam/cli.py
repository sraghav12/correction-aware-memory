"""Offline command interface."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from cam.contracts import ContractError, EvalReport, RuntimeUnavailable, load_config, parse_observation, parse_proposal
from cam.data import generate_dataset, read_jsonl
from cam.evaluate import CorrectnessError, evaluate
from cam.report import write_report


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ContractError(message)


def _check_fixtures(root):
    count = 0
    cases = sorted(path for path in root.iterdir() if path.is_dir())
    if not cases:
        raise ContractError("no fixture cases found")
    for case in cases:
        manifest = json.loads((case / "manifest.json").read_text())
        if set(manifest["files"]) != {"observations.jsonl", "gold.jsonl", "checkpoints.jsonl"}:
            raise ContractError("unknown fixture file set")
        for name, expected_hash in manifest["files"].items():
            if hashlib.sha256((case / name).read_bytes()).hexdigest() != expected_hash:
                raise ContractError(f"fixture hash mismatch: {case.name}/{name}")
        observations, proposals = read_jsonl(case / "observations.jsonl"), read_jsonl(case / "gold.jsonl")
        if len(observations) != len(proposals):
            raise ContractError("fixture observation/proposal count mismatch")
        for raw in observations:
            observation = parse_observation(raw)
            if observation.value not in manifest["allowed_predicates"].get(observation.predicate, []):
                raise ContractError("fixture outside predicate/value vocabulary")
        for raw in proposals:
            parse_proposal(raw)
        count += len(observations)
    return {"cases": len(cases), "observations": count}


def main(argv=None) -> int:
    parser = Parser(description="Auditable correction-aware memory, offline first")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "evaluate", "train"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", type=Path, required=True)
        sub.add_argument("--out", type=Path, required=True)
        sub.add_argument("--offline", action="store_true")
    check = commands.add_parser("check")
    check.add_argument("--fixtures", type=Path, required=True)
    check.add_argument("--offline", action="store_true")
    report = commands.add_parser("report")
    report.add_argument("--run", type=Path, required=True)
    report.add_argument("--out", type=Path, required=True)
    report.add_argument("--offline", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.command == "check":
            result = _check_fixtures(args.fixtures)
        elif args.command == "report":
            saved = EvalReport(args.run, json.loads((args.run / "metrics.json").read_text()), json.loads((args.run / "manifest.json").read_text()))
            result = {"report": str(write_report(saved, args.out))}
        else:
            config = load_config(args.config, args.out)
            if args.command == "generate":
                result = asdict(generate_dataset(config.data, args.out))
            elif args.command == "train":
                raise RuntimeUnavailable("Adapter training is gated in this offline release. The annotated pilot is solved by rules; human label review and a justified model experiment remain pending.")
            else:
                evaluated = evaluate(config)
                result = {"run": str(args.out), "metrics": evaluated.metrics}
                if config.proposer.get("kind") == "rule" and not evaluated.metrics["correctness_gate_passed"]:
                    print(json.dumps({"status": "correctness_gate_failed", **result}))
                    return 4
        print(json.dumps({"status": "ok", **result}, sort_keys=True))
        return 0
    except RuntimeUnavailable as error:
        print(json.dumps({"status": "unavailable", "error": str(error)}))
        return 3
    except CorrectnessError as error:
        print(json.dumps({"status": "correctness_gate_failed", "error": str(error)}))
        return 4
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
