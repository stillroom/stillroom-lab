"""Canonical observations retain typed facts and full provenance."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from services.mapping import Family
from services.ontology import EntityName, StrictModel


class CanonicalRecord(StrictModel):
    record_id: UUID
    entity: EntityName
    canonical_id: str = Field(min_length=1)
    data: dict[str, Any]
    family: Family
    source_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    snapshot_id: UUID
    mapping_version: str
    ontology_version: Literal["v0.1.0"]


class Snapshot(StrictModel):
    snapshot_id: UUID
    family: Family
    source_locator: str
    observed_at: date
    observation_basis: str
    retrieved_at: AwareDatetime
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    mapping_version: str
    ontology_version: Literal["v0.1.0"]

    def is_stale(self, *, as_of: date, max_age_days: int) -> bool:
        if max_age_days < 0 or as_of < self.observed_at:
            raise ValueError("Freshness requires a nonnegative age and non-future observation")
        return (as_of - self.observed_at).days > max_age_days


class ResolutionCandidate(StrictModel):
    candidate_id: UUID
    left_source_id: str
    right_source_id: str
    left_record_id: UUID
    right_record_id: UUID
    reason: str
    state: Literal["pending", "rejected"]
    reviewed_by: str | None
    reviewed_at: AwareDatetime | None


class ResolutionDecision(StrictModel):
    decision_id: int
    candidate_id: UUID
    decision: Literal["merge-rejected", "reject"]
    actor: str
    decided_at: AwareDatetime


def canonical_value(value: object, kind: str) -> object:
    if kind.startswith("optional:"):
        if value is None or value == "":
            return None
        kind = kind.removeprefix("optional:")
    if kind == "string" and isinstance(value, str) and value.strip():
        return value
    if kind == "list:string" and isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    if kind == "date" and isinstance(value, (str, date)) and not isinstance(value, datetime):
        return date.fromisoformat(str(value)).isoformat()
    if kind == "decimal" and isinstance(value, str):
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Invalid decimal source value") from exc
        if number.is_finite():
            return str(number)
    raise ValueError(f"Invalid or missing canonical {kind} value")
