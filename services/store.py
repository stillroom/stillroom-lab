"""Transactional Postgres persistence for the local, operator-controlled lab."""
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from services.mapping import MappingContract
from services.records import CanonicalRecord, Snapshot, ResolutionCandidate, ResolutionDecision
from services.ontology import Ontology, StrictModel

DSN = "host=127.0.0.1 port=55432 dbname=lab user=lab password=lab-scratch-only connect_timeout=5"


def digest(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class OntologyAudit(StrictModel):
    ontology: Ontology
    digest: str
    registered_at: datetime


class MappingApproval(StrictModel):
    contract: MappingContract
    digest: str
    state: Literal["proposed", "approved", "rejected"]
    approved_by: str | None
    approved_at: datetime | None


class Store:
    def __init__(self, *, schema: str = "stillroom_v02") -> None:
        self.schema = schema
        with psycopg.connect(DSN) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        with self.transaction() as db:
            db.execute(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(DSN, row_factory=dict_row) as conn:
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(self.schema)))
            yield conn

    def register_ontology(self, ontology: Ontology) -> None:
        data = ontology.model_dump(mode="json")
        with self.transaction() as db:
            db.execute("INSERT INTO ontology_versions (version,digest,definition) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                       (ontology.version, digest(data), Jsonb(data)))
            row = db.execute("SELECT digest FROM ontology_versions WHERE version=%s", (ontology.version,)).fetchone()
            if row is None or row["digest"] != digest(data):
                raise ValueError("Ontology version is immutable; content differs")

    def ontology_version(self, version: str) -> OntologyAudit:
        with self.transaction() as db:
            row = db.execute("SELECT definition AS ontology,digest,registered_at FROM ontology_versions WHERE version=%s", (version,)).fetchone()
            if row is None:
                raise ValueError("Ontology version not registered")
            return OntologyAudit.model_validate(row)

    def register_mapping(self, mapping: MappingContract) -> None:
        data = mapping.model_dump(mode="json")
        with self.transaction() as db:
            db.execute("INSERT INTO mappings (family,version,ontology_version,digest,contract) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                       (mapping.family, mapping.version, mapping.ontology_version, digest(data), Jsonb(data)))
            row = db.execute("SELECT digest FROM mappings WHERE family=%s AND version=%s", (mapping.family, mapping.version)).fetchone()
            if row is None or row["digest"] != digest(data):
                raise ValueError("Mapping version is immutable; content differs")

    def mapping(self, family: str, version: str) -> MappingApproval:
        with self.transaction() as db:
            row = db.execute("SELECT contract,digest,state,approved_by,approved_at FROM mappings WHERE family=%s AND version=%s",
                             (family, version)).fetchone()
            if row is None:
                raise ValueError("Mapping not registered")
            return MappingApproval.model_validate(row)

    def approve_mapping(self, family: str, version: str, actor: str) -> None:
        if not actor.strip():
            raise ValueError("Approval requires a named operator")
        with self.transaction() as db:
            row = db.execute("UPDATE mappings SET state='approved',approved_by=%s,approved_at=clock_timestamp() WHERE family=%s AND version=%s AND state='proposed' RETURNING family",
                             (actor, family, version)).fetchone()
            if row is None:
                raise ValueError("Only a registered proposed mapping can be approved")

    def resolution_candidates(self) -> list[ResolutionCandidate]:
        with self.transaction() as db:
            return [ResolutionCandidate.model_validate(row) for row in
                    db.execute("SELECT * FROM resolution_candidates ORDER BY left_source_id,right_source_id").fetchall()]

    def resolution_decisions(self, candidate_id: UUID) -> list[ResolutionDecision]:
        with self.transaction() as db:
            return [ResolutionDecision.model_validate(row) for row in db.execute(
                "SELECT * FROM resolution_decisions WHERE candidate_id=%s ORDER BY decision_id", (candidate_id,)).fetchall()]

    def resolve_candidate(self, candidate_id: UUID, decision: str, actor: str) -> None:
        if not actor.strip() or decision not in {"merge", "reject"}:
            raise ValueError("A named operator and merge/reject decision are required")
        with self.transaction() as db:
            row = db.execute("SELECT state FROM resolution_candidates WHERE candidate_id=%s FOR UPDATE", (candidate_id,)).fetchone()
            if row is None or row["state"] != "pending":
                raise ValueError("Candidate must be pending")
            db.execute("INSERT INTO resolution_decisions (candidate_id,decision,actor) VALUES (%s,%s,%s)",
                       (candidate_id, "merge-rejected" if decision == "merge" else "reject", actor))
            if decision == "reject":
                db.execute("UPDATE resolution_candidates SET state='rejected',reviewed_by=%s,reviewed_at=clock_timestamp() WHERE candidate_id=%s",
                           (actor, candidate_id))
        # Raise after committing the denied attempt, so its audit evidence survives.
        if decision == "merge":
            raise ValueError("Cannot merge ambiguous customers; candidate remains pending")

    def snapshots(self) -> list[Snapshot]:
        with self.transaction() as db:
            return [Snapshot.model_validate(row) for row in
                    db.execute("SELECT * FROM snapshots ORDER BY observed_at,snapshot_id").fetchall()]

    def records(self) -> list[CanonicalRecord]:
        with self.transaction() as db:
            return [CanonicalRecord.model_validate(row) for row in
                    db.execute("SELECT * FROM canonical_records ORDER BY entity,canonical_id").fetchall()]
