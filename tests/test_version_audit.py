from copy import deepcopy

import pytest

from services.application import Application
from services.mapping import load_mapping, validate_mapping
from services.store import Store
from test_ingestion import ROOT


def test_versions_are_auditable_and_same_version_cannot_be_redefined(store: Store) -> None:
    app = Application(store)
    contract = load_mapping(ROOT / "sources/mappings/crm.v0.1.0.yaml", app.ontology)
    app.register_mapping(contract)
    app.approve_mapping("crm", "v0.1.0", actor="test-operator")
    app.ingest("crm", "v0.1.0")
    audit = Store(schema=store.schema).ontology_version("v0.1.0")
    assert audit.ontology.version == "v0.1.0"
    assert set(audit.ontology.entities) == {"Customer", "Account", "Invoice", "Payment", "Opportunity", "Ticket", "Communication", "Policy"}
    assert len(audit.digest) == 64
    assert audit.registered_at.utcoffset() is not None
    assert len(store.mapping("crm", "v0.1.0").digest) == 64
    altered = deepcopy(contract.model_dump())
    altered["records"][0]["fields"]["email"] = "name"
    with pytest.raises(ValueError, match="immutable"):
        app.register_mapping(validate_mapping(altered, app.ontology))
    changed_ontology = app.ontology.model_dump()
    changed_ontology["entities"]["Customer"]["description"] = "Changed meaning"
    with pytest.raises(ValueError, match="immutable"):
        store.register_ontology(type(app.ontology).model_validate(changed_ontology))
    assert store.mapping("crm", "v0.1.0").contract.records[0].fields["email"] == "email"
    assert store.mapping("crm", "v0.1.0").approved_by == "test-operator"
