"""Immutable SQLite memory ledger and temporal projection."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from cam.contracts import (CandidateVersion, CommitResult, ContractError, DecisionRequest,
                           EvidenceRef, FactView, Observation, Proposal, canonical_json,
                           digest, parse_observation, utc)
from cam.policy import heads, validate


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO metadata VALUES ('revision', '0');
            INSERT OR IGNORE INTO metadata VALUES ('observed_high_water', '');
            CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (observation_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY, attempt_key TEXT UNIQUE NOT NULL,
                observation_id TEXT NOT NULL, observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
                request TEXT NOT NULL, proposal TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (
                version_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations,
                entity_id TEXT NOT NULL, predicate TEXT NOT NULL, value TEXT, effective_at TEXT NOT NULL,
                parent_version_id TEXT REFERENCES versions, event_sequence INTEGER NOT NULL REFERENCES events);
            CREATE TABLE IF NOT EXISTS supports (
                version_id TEXT NOT NULL REFERENCES versions, source_id TEXT NOT NULL REFERENCES sources,
                observation_id TEXT NOT NULL REFERENCES observations, event_sequence INTEGER NOT NULL REFERENCES events,
                PRIMARY KEY (version_id, source_id));
            CREATE INDEX IF NOT EXISTS versions_key ON versions(entity_id, predicate);
        """)
        for table in ("sources", "observations", "events", "versions", "supports"):
            for operation in ("UPDATE", "DELETE"):
                self.connection.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable ledger'); END")

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @contextmanager
    def _transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def _metadata(self, key):
        return self.connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()[0]

    def _register(self, observation):
        existing = self.connection.execute("SELECT payload_sha256 FROM observations WHERE observation_id=?", (observation.observation_id,)).fetchone()
        if existing and existing[0] != digest(observation):
            raise ContractError("observation identity reused with changed payload")
        source = self.connection.execute("SELECT source_sha256, text FROM sources WHERE source_id=?", (observation.source_id,)).fetchone()
        if source and tuple(source) != (observation.source_sha256, observation.text):
            raise ContractError("source identity reused with changed text")
        self.connection.execute("INSERT OR IGNORE INTO sources VALUES (?, ?, ?)", (observation.source_id, observation.source_sha256, observation.text))
        self.connection.execute("INSERT OR IGNORE INTO observations VALUES (?, ?, ?)", (observation.observation_id, digest(observation), canonical_json(observation)))

    def _candidates(self, entity_id, predicate, known_at):
        rows = self.connection.execute("""SELECT v.* FROM versions v JOIN events e ON e.sequence=v.event_sequence
            WHERE v.entity_id=? AND v.predicate=? AND e.observed_at<=? ORDER BY e.sequence""", (entity_id, predicate, known_at)).fetchall()
        versions = []
        for row in rows:
            supporting = self.connection.execute("""SELECT o.payload FROM supports s
                JOIN observations o ON o.observation_id=s.observation_id JOIN events e ON e.sequence=s.event_sequence
                WHERE s.version_id=? AND e.observed_at<=? ORDER BY s.event_sequence""", (row["version_id"], known_at)).fetchall()
            observations = [parse_observation(json.loads(item[0])) for item in supporting]
            refs = tuple(EvidenceRef(o.observation_id, o.source_id, o.source_sha256, o.evidence_start, o.evidence_end, o.observed_at) for o in observations)
            versions.append(CandidateVersion(row["version_id"], row["value"], row["effective_at"], row["parent_version_id"], tuple(o.observation_id for o in observations), refs))
        return tuple(versions)

    def snapshot(self, observation: Observation) -> DecisionRequest:
        observation = parse_observation(asdict(observation))
        with self._transaction():
            self._register(observation)
            candidates = self._candidates(observation.entity_id, observation.predicate, observation.observed_at)
            if len(candidates) > 16:
                raise ContractError("CONTEXT_LIMIT")
            return DecisionRequest(observation, int(self._metadata("revision")), candidates)

    @staticmethod
    def _result(raw):
        payload = json.loads(raw)
        payload["validation_codes"] = tuple(payload["validation_codes"])
        return CommitResult(**payload)

    def commit(self, request: DecisionRequest, proposal: Proposal) -> CommitResult:
        attempt_key = digest({"request": asdict(request), "proposal": asdict(proposal)})
        observation = request.observation
        with self._transaction():
            prior = self.connection.execute("SELECT result FROM events WHERE attempt_key=?", (attempt_key,)).fetchone()
            if prior:
                return self._result(prior[0])
            registered = self.connection.execute("SELECT payload_sha256 FROM observations WHERE observation_id=?", (observation.observation_id,)).fetchone()
            matches = registered is not None and registered[0] == digest(observation)
            if matches:
                for row in self.connection.execute("SELECT result FROM events WHERE observation_id=? ORDER BY sequence", (observation.observation_id,)):
                    result = self._result(row[0])
                    if result.status == "committed":
                        return result
            before = int(self._metadata("revision"))
            codes = []
            if not matches:
                codes.append("OBSERVATION_MISMATCH")
            elif request.snapshot_revision != before:
                codes.append("REVISION_CONFLICT")
            elif request.candidate_versions != self._candidates(observation.entity_id, observation.predicate, observation.observed_at):
                codes.append("SNAPSHOT_MISMATCH")
            if observation.observed_at < self._metadata("observed_high_water"):
                codes.append("OBSERVED_TIME_ORDER")
            codes.extend(validate(request, proposal))
            sequence = self.connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events").fetchone()[0]
            fact_changed = not codes and proposal.action in ("create", "supersede", "update")
            support_new = not codes and proposal.action == "reinforce" and not self.connection.execute(
                "SELECT 1 FROM supports WHERE version_id=? AND source_id=?", (proposal.target_version_id, observation.source_id)).fetchone()
            after = before + int(bool(fact_changed or support_new))
            result = CommitResult(f"e:{sequence}", "rejected" if codes else "committed", tuple(dict.fromkeys(codes)), before, after, fact_changed)
            self.connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                sequence, attempt_key, observation.observation_id, observation.observed_at,
                datetime.now(timezone.utc).isoformat(), canonical_json(request), canonical_json(proposal), canonical_json(result)))
            if fact_changed:
                version_id = f"v:{observation.observation_id}"
                self.connection.execute("INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                    version_id, observation.observation_id, observation.entity_id, observation.predicate, observation.value,
                    observation.effective_at, proposal.target_version_id if proposal.action == "update" else None, sequence))
            else:
                version_id = proposal.target_version_id
            if fact_changed or support_new:
                self.connection.execute("INSERT INTO supports VALUES (?, ?, ?, ?)", (version_id, observation.source_id, observation.observation_id, sequence))
            self.connection.execute("UPDATE metadata SET value=? WHERE key='revision'", (str(after),))
            if matches:
                self.connection.execute("UPDATE metadata SET value=? WHERE key='observed_high_water'", (max(observation.observed_at, self._metadata("observed_high_water")),))
            return result

    def view(self, entity_id: str, predicate: str, *, effective_as_of: str, known_at: str) -> FactView:
        effective_as_of, known_at = utc(effective_as_of), utc(known_at)
        # One read transaction prevents a concurrent commit from mixing projection rows.
        with self._transaction():
            timeline = heads(self._candidates(entity_id, predicate, known_at))
            eligible = [boundary for boundary in timeline if boundary <= effective_as_of]
            if not eligible:
                return FactView(None, None, "absent", None, None, ())
            boundary = max(eligible)
            chosen = timeline[boundary]
            later = [time for time in timeline if time > boundary]
            return FactView(chosen.version_id, chosen.value, "retracted" if chosen.value is None else "active", boundary,
                            min(later) if later else None, tuple(sorted(ref.source_id for ref in chosen.source_refs)))
