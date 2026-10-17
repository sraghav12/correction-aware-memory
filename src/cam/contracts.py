"""Strict public contracts for atomic correction memory."""

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path


class ContractError(ValueError):
    """Invalid envelope, schema, or immutable identity."""


class RuntimeUnavailable(RuntimeError):
    """A requested optional experiment is unavailable in this release."""


def canonical_json(value) -> str:
    return json.dumps(asdict(value) if is_dataclass(value) else value,
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                      default=_json_default)


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"unsupported JSON type: {type(value).__name__}")


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


@dataclass(frozen=True)
class DataConfig:
    manifest: Path | None = None
    split: str = "pilot"
    seed: int = 11
    trajectories: int = 50

    def __post_init__(self):
        if self.split not in ("pilot", "train", "development", "test", "style_transfer"):
            raise ContractError("unknown split")
        if type(self.seed) is not int or type(self.trajectories) is not int or not 1 <= self.trajectories <= 10000:
            raise ContractError("invalid seed or trajectory count")


@dataclass(frozen=True)
class DatasetManifest:
    schema_version: int
    dataset_id: str
    seed: int
    split: str
    trajectory_count: int
    event_count: int
    files: dict[str, str]
    generator_version: str = "original-world-v1"
    license: str = "CC0-1.0"
    review_status: str = "not_human_reviewed"


@dataclass(frozen=True)
class EvalConfig:
    data: DataConfig
    output_dir: Path
    proposer: dict = field(default_factory=lambda: {"kind": "rule"})
    generation: dict = field(default_factory=dict)
    training: dict = field(default_factory=dict)
    evaluation: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EvalReport:
    run_dir: Path
    metrics: dict
    manifest: dict


def load_config(path: Path, output_dir: Path) -> EvalConfig:
    raw = json.loads(path.read_text())
    allowed = {"schema_version", "data", "proposer", "generation", "training", "evaluation"}
    if not isinstance(raw, dict) or set(raw) - allowed or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ContractError("unknown config fields or schema_version")
    schemas = {
        "data": {"manifest", "split", "seed", "trajectories"},
        "proposer": {"kind", "model_id", "revision", "adapter_path", "device"},
        "generation": {"max_input_tokens", "max_new_tokens", "enable_thinking", "do_sample", "decoding"},
        "training": {"gate", "rank", "alpha", "dropout", "learning_rate", "epochs", "microbatch", "accumulation", "max_sequence", "seed"},
        "evaluation": {"seeds", "bootstrap_count", "qa_mode"},
    }
    for key, keys in schemas.items():
        section = raw.get(key, {})
        if not isinstance(section, dict) or set(section) - keys:
            raise ContractError(f"unknown {key} config fields")
    settings = dict(raw.get("data", {}))
    if settings.get("manifest"):
        settings["manifest"] = (path.parent / settings["manifest"]).resolve()
    data = DataConfig(**settings)
    proposer = raw.get("proposer", {"kind": "rule"})
    if proposer.get("kind") not in ("rule", "qwen"):
        raise ContractError("unknown proposer")
    if proposer.get("kind") == "qwen" and not re.fullmatch(r"[0-9a-f]{40}", proposer.get("revision") or ""):
        raise ContractError("model runs require a pinned 40-hex revision")
    return EvalConfig(data, output_dir, proposer, raw.get("generation", {}), raw.get("training", {}), raw.get("evaluation", {}))
