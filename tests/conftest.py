import hashlib
import json
from pathlib import Path

import pytest


def make_observation(*, oid="o1", value="preliminary", day=1, effective_day=1,
                     authority="official", corrects=None, authorized=False,
                     entity="experiment-17", source=None, text=None):
    text = text or f"Release state: {value}, effective October {effective_day}."
    return {
        "observation_id": oid, "trajectory_id": "t1", "source_id": source or f"source-{oid}",
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "entity_id": entity, "predicate": "release_state", "value": value,
        "effective_at": f"2026-10-{effective_day:02d}T00:00:00Z" if effective_day else None,
        "observed_at": f"2026-10-{day:02d}T00:00:00Z", "evidence_start": 0,
        "evidence_end": len(text), "text": text, "authority": authority,
        "corrects_observation_id": corrects, "correction_authorized": authorized,
    }


def make_proposal(observation, action="create", target=None, reason="initial_fact", review=False):
    return {
        "action": action, "target_version_id": target,
        "value": None if action == "no_op" else observation["value"],
        "effective_at": None if action == "no_op" else observation["effective_at"],
        "source_id": observation["source_id"], "evidence_start": observation["evidence_start"],
        "evidence_end": observation["evidence_end"], "reason_code": reason,
        "review_required": review,
    }


@pytest.fixture
def observation_payload():
    return make_observation()


@pytest.fixture
def proposal_payload(observation_payload):
    return make_proposal(observation_payload)


@pytest.fixture
def canonical_case_dir():
    return Path(__file__).resolve().parents[1] / "data/fixtures/canonical"


def apply_case(store, case_dir):
    from cam.contracts import parse_observation, parse_proposal
    observations = [json.loads(line) for line in (case_dir / "observations.jsonl").read_text().splitlines()]
    proposals = [json.loads(line) for line in (case_dir / "gold.jsonl").read_text().splitlines()]
    return [store.commit(store.snapshot(parse_observation(o)), parse_proposal(p))
            for o, p in zip(observations, proposals, strict=True)]
