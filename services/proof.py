"""Required evidence envelope; source observations are not completeness claims."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime

from services.ontology import StrictModel


class TicketEvidence(StrictModel):
    customer_id: str
    status: str
    subject: str


class SourceEvidence(StrictModel):
    payment_absence: bool
    family: str
    conflicts: list[str]
    ticket: TicketEvidence | None
    entity: str
    canonical_id: str
    source_id: str
    snapshot_id: UUID
    retrieved_at: AwareDatetime
    observed_at: date
    mapping_version: str
    ontology_version: str


class ProofManifest(StrictModel):
    source_ids: list[str]
    retrieved_at: AwareDatetime
    snapshot_id: UUID
    ontology_version: str
    mapping_versions: list[str]
    approved_query: str | None
    metric_definition_ref: str | None
    permission_context: dict[str, str] | None
    unresolved_conflicts: list[str]
    sources: list[SourceEvidence]
    caveats: list[str]
    completeness_check: Literal['not_established']
    as_of: date | None
    period_start: date | None
