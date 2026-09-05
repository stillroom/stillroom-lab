from pathlib import Path
from copy import deepcopy

import pytest
import yaml
from pydantic import ValidationError

from services.ontology import load_ontology

ROOT = Path(__file__).resolve().parents[1]


def test_pinned_ontology_defines_business_meaning_not_source_or_query_rules() -> None:
    ontology = load_ontology(ROOT / "ontology/v0.1.0.yaml")
    assert ontology.version == "v0.1.0"
    assert set(ontology.entities) == {
        "Customer", "Account", "Invoice", "Payment", "Opportunity", "Ticket",
        "Communication", "Policy",
    }
    assert {(r.source, r.target) for r in ontology.relationships} >= {
        ("Customer", "Account"), ("Invoice", "Customer"), ("Payment", "Invoice"),
        ("Opportunity", "Customer"), ("Ticket", "Customer"),
        ("Communication", "Customer"), ("Policy", "Policy"),
    }
    assert {name: metric.basis for name, metric in ontology.metrics.items()} == {
        "revenue": "earned", "cash_received": "settled_cash",
        "pipeline": "unwon_opportunities", "overdue_balances": "past_due_outstanding",
    }


def test_invalid_ontology_is_rejected_by_public_loader(tmp_path: Path) -> None:
    original = yaml.safe_load((ROOT / "ontology/v0.1.0.yaml").read_text())
    invalid = []
    data = deepcopy(original)
    data["version"] = "v0.2.0"
    invalid.append(data)
    data = deepcopy(original)
    del data["entities"]["Payment"]
    invalid.append(data)
    data = deepcopy(original)
    data["relationships"] = []
    invalid.append(data)
    data = deepcopy(original)
    data["metrics"]["revenue"]["basis"] = "settled_cash"
    invalid.append(data)
    data = deepcopy(original)
    data["source_mapping"] = {"table": "invoices"}
    invalid.append(data)
    data = deepcopy(original)
    data["entities"]["Customer"]["fields"]["id"] = "executable-python"
    invalid.append(data)
    for data in invalid:
        path = tmp_path / "invalid.yaml"
        path.write_text(yaml.safe_dump(data))
        with pytest.raises(ValidationError):
            load_ontology(path)
