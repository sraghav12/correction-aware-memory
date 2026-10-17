import hashlib
import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from cam import contracts as c
from conftest import make_proposal


def test_actions_and_utc_schema(observation_payload):
    observation = c.parse_observation(observation_payload)
    assert observation.authority == "official"
    assert observation.observed_at.endswith("Z")
    assert c.parse_observation({**observation_payload, "observed_at": "2026-10-01T00:00:00+00:00"}) == observation
    for action in ["create", "reinforce", "supersede", "update", "no_op"]:
        payload = make_proposal(observation_payload, action, reason="stale" if action == "no_op" else "initial_fact")
        assert c.parse_proposal(payload).action == action
    for stamp in ["2026-10-01", "2026-10-01T01:00:00+01:00", "yesterday", 3]:
        with pytest.raises(c.ContractError):
            c.parse_observation({**observation_payload, "observed_at": stamp})
    with pytest.raises(FrozenInstanceError):
        observation.value = "published"


@pytest.mark.parametrize("patch", [
    {"source_sha256": "0" * 64}, {"evidence_end": 999}, {"evidence_start": True},
    {"value": 5}, {"authority": "model_asserted"}, {"correction_authorized": 1},
    {"injected_field": "trust me"}, {"observation_id": ""},
])
def test_span_hash_and_unknown_fields(observation_payload, patch):
    with pytest.raises(c.ContractError):
        c.parse_observation({**observation_payload, **patch})


def test_missing_metadata_and_unknown_proposal_fields(observation_payload, proposal_payload):
    del observation_payload["authority"]
    with pytest.raises(c.ContractError):
        c.parse_observation(observation_payload)
    with pytest.raises(c.ContractError):
        c.parse_proposal({**proposal_payload, "sql": "DELETE FROM versions"})
    with pytest.raises(c.ContractError):
        c.parse_proposal({**proposal_payload, "action": "delete"})


def test_same_id_changed_metadata_is_distinct_payload(observation_payload):
    first = c.parse_observation(observation_payload)
    changed = c.parse_observation({**observation_payload, "authority": "informal"})
    assert first.observation_id == changed.observation_id
    assert first.source_sha256 == changed.source_sha256
    assert c.digest(first) != c.digest(changed)


def test_fixture_hashes_unicode_and_gold_separation(canonical_case_dir):
    cases = sorted(canonical_case_dir.parent.iterdir())
    assert len(cases) == 12
    actions = set()
    for case in cases:
        for line in (case / "observations.jsonl").read_text().splitlines():
            raw = json.loads(line)
            parsed = c.parse_observation(raw)
            assert "action" not in asdict(parsed)
            assert parsed.source_sha256 == hashlib.sha256(parsed.text.encode()).hexdigest()
            assert parsed.text[parsed.evidence_start:parsed.evidence_end]
        for line in (case / "gold.jsonl").read_text().splitlines():
            actions.add(c.parse_proposal(json.loads(line)).action)
    assert actions == {"create", "reinforce", "supersede", "update", "no_op"}
