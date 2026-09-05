"""Versioned correspondence; source adapters are fixed, never supplied code/SQL."""
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
import yaml

from services.ontology import EntityName, Ontology, StrictModel

Family = Literal["crm", "billing", "support", "email", "policy"]
SOURCE_FIELDS = {
    "crm": {"customers": {"id", "client_id", "name", "email", "access"},
            "opportunities": {"id", "customer_id", "description", "amount"}},
    "billing": {"invoices": {"id", "customer_id", "amount", "issued_at", "due_at"},
                "payments": {"id", "invoice_id", "amount", "paid_at", "kind"}},
    "support": {"tickets": {"id", "customer_id", "status", "invoice_id", "reported_due_at", "snapshot_at", "subject"}},
    "email": {"messages": {"Message-ID", "From", "Subject", "Customer-ID", "Date", "body"}},
    "policy": {"documents": {"id", "created", "owner", "status", "related", "body"}},
}


class RecordMapping(StrictModel):
    dataset: str
    entity: EntityName
    source_id: str
    fields: dict[str, str]
    observation_field: str | None = None


class MappingContract(StrictModel):
    family: Family
    version: str = Field(pattern=r"^v[0-9]+\.[0-9]+\.[0-9]+$")
    ontology_version: Literal["v0.1.0"]
    proposed_by: str = Field(min_length=1, pattern=r"\S")
    proposal_origin: Literal["ai", "human"]
    approval_state: Literal["proposed"]
    records: list[RecordMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def complete_family(self) -> Self:
        datasets = {record.dataset for record in self.records}
        if datasets != set(SOURCE_FIELDS[self.family]):
            raise ValueError("Mapping must cover every dataset of the source family")
        return self


def validate_mapping(data: object, ontology: Ontology) -> MappingContract:
    mapping = MappingContract.model_validate(data)
    seen: set[tuple[str, str]] = set()
    for record in mapping.records:
        source = SOURCE_FIELDS[mapping.family].get(record.dataset)
        if source is None:
            raise ValueError("Unknown source dataset")
        if not set(record.fields.values()) <= source or record.source_id not in source:
            raise ValueError("Unknown source field")
        if record.observation_field is not None and record.observation_field not in source:
            raise ValueError("Unknown observation source field")
        if set(record.fields) != set(ontology.entities[record.entity].fields):
            raise ValueError("Mapping must cover exactly the canonical fields")
        identity_field = "Message-ID" if mapping.family == "email" else "id"
        canonical_identity = "client_id" if record.entity == "Account" else identity_field
        if record.source_id != identity_field or record.fields.get("id") != canonical_identity:
            raise ValueError("Mappings must preserve stable source identity, never display names")
        key = (record.dataset, record.entity)
        if key in seen:
            raise ValueError("Duplicate entity mapping")
        seen.add(key)
    return mapping


def load_mapping(path: Path, ontology: Ontology) -> MappingContract:
    return validate_mapping(yaml.safe_load(path.read_text(encoding="utf-8")), ontology)
