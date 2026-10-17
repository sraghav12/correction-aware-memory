"""Reproduce the four-event correction trace without model dependencies."""

from dataclasses import asdict
from pathlib import Path

from cam.contracts import parse_observation
from cam.data import prepare_output, read_jsonl, write_json
from cam.evaluate import CorrectnessError
from cam.policy import propose_rule
from cam.store import Store


def canonical_trace(out_dir: Path) -> Path:
    fixture = Path(__file__).resolve().parents[2] / "data/fixtures/canonical"
    prepare_output(out_dir)
    events, queries = [], []
    with Store(out_dir / "memory.sqlite") as store:
        for raw in read_jsonl(fixture / "observations.jsonl"):
            request = store.snapshot(parse_observation(raw))
            proposal = propose_rule(request)
            result = store.commit(request, proposal)
            if result.status != "committed":
                raise CorrectnessError(f"canonical demo rejected: {result.validation_codes}")
            events.append({"observation": raw, "proposal": asdict(proposal), "commit": asdict(result)})
        for query in read_jsonl(fixture / "checkpoints.jsonl"):
            selected = store.view("experiment-17", "release_state", effective_as_of=query["effective_as_of"], known_at=query["known_at"])
            if selected.value != query["value"]:
                raise CorrectnessError("canonical temporal query does not match authored expectation")
            queries.append({**query, "selected": asdict(selected)})
    path = out_dir / "trace.json"
    write_json(path, {"schema_version": 1, "events": events, "queries": queries,
                      "model_status": "not_run", "adapter_status": "not_trained", "review_status": "not_human_reviewed"})
    return path
