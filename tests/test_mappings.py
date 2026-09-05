from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from services.mapping import load_mapping, validate_mapping
from services.ontology import load_ontology
from services.store import Store
from services.application import Application, UnapprovedMapping
from services.api import create_app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_five_contracts_validate_field_correspondence_and_explicit_proposal_state() -> None:
    ontology = load_ontology(ROOT / "ontology/v0.1.0.yaml")
    contracts = [load_mapping(ROOT / f"sources/mappings/{family}.v0.1.0.yaml", ontology)
                 for family in ("crm", "billing", "support", "email", "policy")]
    assert {m.family for m in contracts} == {"crm", "billing", "support", "email", "policy"}
    assert all(m.version == "v0.1.0" and m.ontology_version == "v0.1.0" for m in contracts)
    assert all(m.approval_state == "proposed" for m in contracts)
    assert contracts[0].records[0].fields["account_id"] == "client_id"
    assert contracts[1].records[1].fields["amount"] == "amount"
    data = yaml.safe_load((ROOT / "sources/mappings/crm.v0.1.0.yaml").read_text())
    data["records"][0]["fields"]["account_id"] = "nonexistent_column"
    with pytest.raises(ValueError, match="source field"):
        validate_mapping(data, ontology)
    data["approval_state"] = "approved"
    with pytest.raises(ValidationError):
        validate_mapping(data, ontology)
    data["records"] = [r for r in data["records"] if r["dataset"] == "customers"]
    data["approval_state"] = "proposed"
    with pytest.raises(ValidationError, match="every dataset"):
        validate_mapping(data, ontology)


def test_proposed_mappings_are_blocked_and_explicit_approval_survives_reopen(store: Store) -> None:
    app = Application(store)
    for family in ("crm", "billing", "support", "email", "policy"):
        mapping = load_mapping(ROOT / f"sources/mappings/{family}.v0.1.0.yaml", app.ontology)
        app.register_mapping(mapping)
        with pytest.raises(UnapprovedMapping):
            app.ingest(family, "v0.1.0")
        with TestClient(create_app(app)) as client:
            response = client.post("/ingestions", json={"family": family, "mapping_version": "v0.1.0"})
            assert response.status_code == 409
    with pytest.raises(ValueError, match="named operator"):
        app.approve_mapping("crm", "v0.1.0", actor="  ")
    assert store.records() == []
    app.approve_mapping("crm", "v0.1.0", actor="test-operator")
    reopened = Store(schema=store.schema)
    approval = reopened.mapping("crm", "v0.1.0")
    assert approval.state == "approved"
    assert approval.approved_by == "test-operator"
    assert approval.approved_at is not None and approval.approved_at.utcoffset() is not None
    assert approval.contract.proposal_origin == "ai"


def test_mapping_cannot_replace_stable_identity_with_a_display_name() -> None:
    ontology = load_ontology(ROOT / "ontology/v0.1.0.yaml")
    data = yaml.safe_load((ROOT / "sources/mappings/crm.v0.1.0.yaml").read_text())
    data["records"][0]["fields"]["id"] = "name"
    with pytest.raises(ValueError, match="identity"):
        validate_mapping(data, ontology)
