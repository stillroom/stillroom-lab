"""Business meaning only; no source columns or executable query definitions."""
from pathlib import Path
from typing import Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, model_validator
import yaml

EntityName = Literal["Customer", "Account", "Invoice", "Payment", "Opportunity", "Ticket", "Communication", "Policy"]
PINNED_VERSION = "v0.1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityDefinition(StrictModel):
    description: str
    fields: dict[str, Literal["string", "date", "decimal", "list:string", "optional:string", "optional:date"]]


class Relationship(StrictModel):
    name: str
    source: EntityName
    target: EntityName
    cardinality: Literal["many-to-one", "many-to-many"]
    meaning: str


class MetricDefinition(StrictModel):
    basis: Literal["earned", "settled_cash", "unwon_opportunities", "past_due_outstanding"]
    definition: str
    caveats: list[str]


class Ontology(StrictModel):
    version: Literal["v0.1.0"]
    entities: dict[EntityName, EntityDefinition]
    relationships: list[Relationship]
    metrics: dict[Literal["revenue", "cash_received", "pipeline", "overdue_balances"], MetricDefinition]


    @model_validator(mode="after")
    def complete_meaning(self) -> Self:
        if set(self.entities) != set(get_args(EntityName)):
            raise ValueError("All eight v0 entities are required")
        required = {
            ("Customer", "Account"), ("Invoice", "Customer"), ("Payment", "Invoice"),
            ("Opportunity", "Customer"), ("Ticket", "Customer"), ("Ticket", "Invoice"),
            ("Communication", "Customer"), ("Policy", "Policy"),
        }
        if not required <= {(r.source, r.target) for r in self.relationships}:
            raise ValueError("Required business relationships are missing")
        expected = {"revenue": "earned", "cash_received": "settled_cash",
                    "pipeline": "unwon_opportunities", "overdue_balances": "past_due_outstanding"}
        if {k: v.basis for k, v in self.metrics.items()} != expected:
            raise ValueError("The four metrics must retain distinct accounting bases")
        return self


def load_ontology(path: Path) -> Ontology:
    return Ontology.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
