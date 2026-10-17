"""Strict public contracts for atomic correction memory."""

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import re


class ContractError(ValueError):
    """Invalid envelope, schema, or immutable identity."""


def canonical_json(value) -> str:
    return json.dumps(asdict(value) if is_dataclass(value) else value,
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ContractError("timestamp must be a timezone-aware UTC RFC3339 instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError("invalid UTC instant") from error
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    trajectory_id: str
    source_id: str
    source_sha256: str
    entity_id: str
    predicate: str
    value: str | None
    effective_at: str | None
    observed_at: str
    evidence_start: int
    evidence_end: int
    text: str
    authority: str
    corrects_observation_id: str | None
    correction_authorized: bool


@dataclass(frozen=True)
class Proposal:
    action: str
    target_version_id: str | None
    value: str | None
    effective_at: str | None
    source_id: str
    evidence_start: int
    evidence_end: int
    reason_code: str
    review_required: bool


@dataclass(frozen=True)
class EvidenceRef:
    observation_id: str
    source_id: str
    source_sha256: str
    evidence_start: int
    evidence_end: int
    observed_at: str


@dataclass(frozen=True)
class CandidateVersion:
    version_id: str
    value: str | None
    effective_at: str
    parent_version_id: str | None
    observation_ids: tuple[str, ...]
    source_refs: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class DecisionRequest:
    observation: Observation
    snapshot_revision: int
    candidate_versions: tuple[CandidateVersion, ...]


@dataclass(frozen=True)
class CommitResult:
    event_id: str
    status: str
    validation_codes: tuple[str, ...]
    before_revision: int
    after_revision: int
    fact_state_changed: bool


@dataclass(frozen=True)
class FactView:
    version_id: str | None
    value: str | None
    status: str
    effective_at: str | None
    effective_until: str | None
    source_ids: tuple[str, ...]


def _strict(payload: dict, cls) -> dict:
    if not isinstance(payload, dict) or set(payload) != {field.name for field in fields(cls)}:
        raise ContractError(f"{cls.__name__}: missing or unknown fields")
    return dict(payload)


def _string(value, name, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a nonempty string")


def _span(start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ContractError("invalid half-open evidence span")


def parse_observation(payload: dict) -> Observation:
    raw = _strict(payload, Observation)
    for name in ("observation_id", "trajectory_id", "source_id", "entity_id", "predicate", "text"):
        _string(raw[name], name)
    _string(raw["value"], "value", nullable=True)
    _string(raw["corrects_observation_id"], "corrects_observation_id", nullable=True)
    if raw["authority"] not in ("official", "informal") or type(raw["correction_authorized"]) is not bool:
        raise ContractError("invalid authority or correction authorization metadata")
    raw["observed_at"] = utc(raw["observed_at"])
    if raw["effective_at"] is not None:
        raw["effective_at"] = utc(raw["effective_at"])
    _span(raw["evidence_start"], raw["evidence_end"])
    if raw["evidence_end"] > len(raw["text"]):
        raise ContractError("evidence span exceeds source text")
    expected = hashlib.sha256(raw["text"].encode("utf-8")).hexdigest()
    if raw["source_sha256"] != expected:
        raise ContractError("source hash does not match exact UTF-8 source text")
    return Observation(**raw)


def parse_proposal(payload: dict) -> Proposal:
    raw = _strict(payload, Proposal)
    if raw["action"] not in ("create", "reinforce", "supersede", "update", "no_op"):
        raise ContractError("unknown action")
    for name in ("target_version_id", "value"):
        _string(raw[name], name, nullable=True)
    _string(raw["source_id"], "source_id")
    _string(raw["reason_code"], "reason_code")
    _span(raw["evidence_start"], raw["evidence_end"])
    if type(raw["review_required"]) is not bool:
        raise ContractError("review_required must be boolean")
    if raw["effective_at"] is not None:
        raw["effective_at"] = utc(raw["effective_at"])
    if raw["action"] == "no_op":
        if any(raw[key] is not None for key in ("target_version_id", "value", "effective_at")):
            raise ContractError("no_op target/value/date must be null")
        if raw["reason_code"] not in ("stale", "ambiguous", "untrusted", "irrelevant", "duplicate", "retraction_unsupported"):
            raise ContractError("unknown no_op reason")
    return Proposal(**raw)
