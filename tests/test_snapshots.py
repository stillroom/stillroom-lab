from datetime import date

from services.store import Store
from test_ingestion import approved_app


def test_stale_support_observation_is_detected_from_persisted_metadata(store: Store) -> None:
    app = approved_app(store)
    app.ingest("support", "v0.1.0")
    reopened = Store(schema=store.schema)
    snapshots = {s.snapshot_id: s for s in reopened.snapshots()}
    records = {r.canonical_id: r for r in reopened.records()}
    fresh = snapshots[records["T001"].snapshot_id]
    stale = snapshots[records["T002"].snapshot_id]
    assert fresh.observed_at == date(2026, 9, 1)
    assert stale.observed_at == date(2026, 7, 1)
    assert stale.observation_basis == "source:snapshot_at"
    assert stale.retrieved_at == records["T002"].retrieved_at
    assert len(stale.content_digest) == 64
    assert fresh.is_stale(as_of=date(2026, 9, 1), max_age_days=30) is False
    assert stale.is_stale(as_of=date(2026, 9, 1), max_age_days=30) is True
    assert stale.is_stale(as_of=date(2026, 7, 31), max_age_days=30) is False
