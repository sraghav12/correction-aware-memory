from dataclasses import asdict, replace
import sqlite3

import pytest

from cam import store as module
from cam.contracts import ContractError, parse_observation, parse_proposal
from conftest import apply_case, make_observation, make_proposal


@pytest.fixture
def store(tmp_path):
    with module.Store(tmp_path / "memory.sqlite") as instance:
        yield instance


def commit(store, raw, action="create", target=None, reason="initial_fact"):
    return store.commit(store.snapshot(parse_observation(raw)), parse_proposal(make_proposal(raw, action, target, reason)))


def view(store, effective=8, known=10):
    return store.view("experiment-17", "release_state", effective_as_of=f"2026-10-{effective:02d}T00:00:00Z", known_at=f"2026-10-{known:02d}T00:00:00Z")


def test_bitemporal_correction_and_change(store, canonical_case_dir):
    results = apply_case(store, canonical_case_dir)
    assert [result.status for result in results] == ["committed"] * 4
    assert view(store, 8, 9).value == "published"
    assert view(store, 8, 10).value == "withdrawn"
    assert view(store, 2, 10).value == "preliminary"
    assert view(store, 8, 7).value == "preliminary"
    with sqlite3.connect(store.path) as connection:
        original = connection.execute("SELECT value FROM versions WHERE version_id = ?", ("v:o8",)).fetchone()
        assert original == ("published",)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE versions SET value='changed'")


def test_historical_correction_leaves_later_boundary(store):
    commit(store, make_observation())
    commit(store, make_observation(oid="later", value="published", day=8, effective_day=7), "supersede", "v:o1", "new_effective_state")
    commit(store, make_observation(oid="correction", value="withdrawn", day=10, corrects="o1", authorized=True), "update", "v:o1", "authorized_correction")
    assert view(store, 2, 10).value == "withdrawn"
    assert view(store, 8, 10).value == "published"


def test_duplicate_and_revision_conflict(store):
    raw = make_observation()
    request = store.snapshot(parse_observation(raw))
    proposal = parse_proposal(make_proposal(raw))
    first = store.commit(request, proposal)
    assert store.commit(request, proposal) == first
    assert store.commit(store.snapshot(parse_observation(raw)), proposal) == first
    with pytest.raises(ContractError, match="identity"):
        store.snapshot(parse_observation({**raw, "authority": "informal"}))
    assert first.after_revision == 1


def test_rejected_attempt_allows_new_snapshot_retry(store):
    first = make_observation(oid="a", entity="a")
    second = make_observation(oid="b", entity="b")
    ra, rb = [store.snapshot(parse_observation(raw)) for raw in (first, second)]
    pa, pb = [parse_proposal(make_proposal(raw)) for raw in (first, second)]
    assert store.commit(ra, pa).status == "committed"
    rejected = store.commit(rb, pb)
    assert rejected.validation_codes == ("REVISION_CONFLICT",)
    assert rejected.before_revision == rejected.after_revision == 1
    accepted = store.commit(store.snapshot(parse_observation(second)), pb)
    assert accepted.status == "committed"
    assert accepted.event_id != rejected.event_id
    assert store.commit(rb, pb) == rejected
    assert store.commit(store.snapshot(parse_observation(second)), pb) == accepted


def test_invalid_proposal_is_atomic(store):
    raw = make_observation()
    request = store.snapshot(parse_observation(raw))
    forged = parse_proposal({**make_proposal(raw), "value": "published"})
    rejected = store.commit(request, forged)
    assert rejected.status == "rejected"
    assert "VALUE_MISMATCH" in rejected.validation_codes
    assert rejected.after_revision == 0
    assert view(store).status == "absent"
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM supports").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    # Changing model-visible authority after the trusted loader snapshot must fail.
    bad_request = replace(request, observation=replace(request.observation, authority="informal"))
    assert store.commit(bad_request, parse_proposal(make_proposal(raw))).status == "rejected"


def test_retraction_does_not_revive_old_value(store):
    commit(store, make_observation())
    result = commit(store, make_observation(oid="r", value=None, day=2, effective_day=2), "supersede", "v:o1", "retraction")
    assert result.status == "committed"
    assert view(store, 8, 10).status == "retracted"
    assert view(store, 8, 10).value is None
    assert view(store, 1, 10).value == "preliminary"


def test_future_effective_notice(store):
    commit(store, make_observation())
    commit(store, make_observation(oid="f", value="published", day=2, effective_day=15), "supersede", "v:o1", "new_effective_state")
    assert view(store, 8, 10).value == "preliminary"
    assert view(store, 15, 10).value == "published"
    assert view(store, 8, 10).effective_until.startswith("2026-10-15")


def test_observed_time_high_water_mark(store):
    commit(store, make_observation(day=10))
    old = make_observation(oid="old", day=9)
    result = commit(store, old, "no_op", reason="stale")
    assert "OBSERVED_TIME_ORDER" in result.validation_codes
    # Rejected/no-op attempts also advance the ingestion watermark.
    future = make_observation(oid="future", day=15)
    commit(store, future, "no_op", reason="ambiguous")
    between = make_observation(oid="between", day=14)
    assert "OBSERVED_TIME_ORDER" in commit(store, between, "no_op", reason="stale").validation_codes


def test_reinforce_changes_support_revision_only(store):
    commit(store, make_observation())
    second = make_observation(oid="support", day=2)
    result = commit(store, second, "reinforce", "v:o1", "same_fact")
    assert result.status == "committed"
    assert result.after_revision == 2
    assert result.fact_state_changed is False
    assert len(view(store).source_ids) == 2
    repeated = make_observation(oid="repeat", day=3, source=second["source_id"])
    result = commit(store, repeated, "reinforce", "v:o1", "same_fact")
    assert result.after_revision == 2
    assert len(view(store).source_ids) == 2


def test_forged_candidate_snapshot_is_rejected(store):
    raw = make_observation()
    request = store.snapshot(parse_observation(raw))
    commit(store, raw)
    second = make_observation(oid="next", day=2)
    current = store.snapshot(parse_observation(second))
    forged = replace(current, candidate_versions=request.candidate_versions)
    result = store.commit(forged, parse_proposal(make_proposal(second)))
    assert "SNAPSHOT_MISMATCH" in result.validation_codes
