import pytest

from services.store import Store
from test_ingestion import approved_app


def test_duplicate_names_propose_review_without_merging_and_rejection_is_durable(store: Store) -> None:
    app = approved_app(store)
    app.ingest("crm", "v0.1.0")
    customers = [r for r in store.records() if r.entity == "Customer"]
    assert {r.canonical_id for r in customers} == {"C001", "C002", "C003"}
    assert len(customers) == 3
    candidates = store.resolution_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert (candidate.left_source_id, candidate.right_source_id) == ("crm:customers:C001", "crm:customers:C002")
    assert candidate.state == "pending"
    assert candidate.reason == "duplicate-name; identity unresolved"
    with pytest.raises(ValueError, match="ambiguous"):
        app.resolve_candidate(candidate.candidate_id, decision="merge", actor="test-operator")
    assert store.resolution_decisions(candidate.candidate_id)[0].decision == "merge-rejected"
    app.resolve_candidate(candidate.candidate_id, decision="reject", actor="test-operator")
    reopened = Store(schema=store.schema)
    rejected = reopened.resolution_candidates()[0]
    assert rejected.state == "rejected"
    assert rejected.reviewed_by == "test-operator"
    assert rejected.reviewed_at is not None
    assert len([r for r in reopened.records() if r.entity == "Customer"]) == 3
    app.ingest("crm", "v0.1.0")
    assert len(store.resolution_candidates()) == 1
    assert store.resolution_candidates()[0].state == "rejected"
