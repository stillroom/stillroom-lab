# Ticket 02 — local canonical ingestion

## Boundary

FastAPI factory: `services.api.create_app(application)`.
Only `POST /ingestions` is exposed, with a Pydantic body:
`{"family":"crm","mapping_version":"v0.1.0"}`.
Unknown families/fields are rejected, unapproved mappings return HTTP 409.
There are no query, metric, proof, agent or UI endpoints.

This is a **trusted local-operator sandbox**, not a remotely exposed service.
There is no multi-user authentication or ticket-03 permission enforcement.
Do not expose the ASGI app to a network. The database is fixed to
`127.0.0.1:55432`, using ticket-01's public disposable credential. No new Docker
services/extensions were added. Approvals are deliberately not available over
HTTP; the operator uses the application interface below. Actor strings are
operator attestations, not authenticated identities.

## Use from the repository root

Start the existing database with `docker compose up -d --wait`. Source fixtures
must already exist from ticket 01; ingestion never invokes the seed script.
Use `uv run --frozen python` with the following Python application interface:

```python
from pathlib import Path
from services.application import Application
from services.mapping import load_mapping
from services.store import Store

store = Store()  # creates the stillroom_v02 schema in the scratch Postgres
app = Application(store)
contract = load_mapping(Path("sources/mappings/crm.v0.1.0.yaml"), app.ontology)
app.register_mapping(contract)  # proposed only; NEVER auto-approves

# Only after actually reviewing the contract, supply the operator's identity:
app.approve_mapping("crm", "v0.1.0", actor="<reviewing operator>")
app.ingest("crm", "v0.1.0")
records = store.records()
candidates = store.resolution_candidates()
```

Repeat registration/review/ingestion for `billing`, `support`, `email`, `policy`.
Checked-in contracts are AI proposals, not Adam-approved mappings. Test approvals
use `test-operator` in isolated schemas; they do not approve deployment mappings.
`create_app(app)` gives an ASGI application for local hosting or TestClient use.

## Inspection and audit interfaces

- `store.records()` returns typed canonical **observations**, not a deduplicated
  current-state view. A fresh ingestion appends fresh snapshot/observation IDs.
  Source identity remains `family:dataset:source-id`, never display name.
- `store.snapshots()` includes observation date/basis, retrieval time, captured
  file SHA-256, mapping version and ontology version. Each canonical observation
  pins its own snapshot. `snapshot.is_stale(as_of=date(...), max_age_days=30)`
  uses a caller-specified date/threshold, not the current wall clock. Future
  observations and negative thresholds are rejected rather than called fresh.
- Support uses each row's `snapshot_at`. Other ticket-01 sources lack snapshot
  metadata; they use the documented fixed fixture observation date 2026-09-01,
  explicitly labelled `ticket01-fixed-observation`. Policy creation/message dates
  are **not** relabelled as snapshot dates. This fallback is mock-specific, not a
  production connector completeness assertion.
- `store.mapping(family, version)` returns the proposal contract, normalized
  content SHA-256, approval state, actor and timestamp. Re-registering changed
  content under that version fails; re-registration never overwrites approval.
- `store.ontology_version("v0.1.0")` returns meaning, digest and registration time.
- `store.resolution_candidates()` surfaces pending and rejected pairs, with
  source IDs and pinned evidence-record IDs. Name similarity only proposes
  review, including across client partitions. No customer merge is implemented.
- `app.resolve_candidate(id, decision="merge", actor=...)` refuses ambiguity and
  records `merge-rejected` before raising. The candidate stays pending.
  `decision="reject"` persists a reviewer rejection. Decisions are inspectable
  with `store.resolution_decisions(id)`. Re-ingestion never resets a rejection.

## Integrity and source safety

Each family ingestion is one transaction: malformed typed facts roll back that
family, including snapshots/candidates. Canonical JSONB stores validated typed
facts (date strings, exact Decimal strings, nullable IDs); no floating-point
money or metric arithmetic. Missing IDs and conflicting facts are retained,
not guessed away. Account derives from CRM `client_id` and carries provenance to
its originating customer row; it is a client partition, not a bank account.
Relationships are declared in the ontology and represented by canonical reference
fields. Missing and dangling references are not silently repaired.

Snapshot foreign keys tie provenance together; database triggers reject
unapproved mappings for snapshot/canonical inserts. DB schema owner access is
trusted administration, not a tamper-proof audit or hostile-DB security boundary.

Adapters read fixed files only. SQLite is deserialized from captured source bytes
into a query-only in-memory SQLite connection, eliminating source journals and
ensuring the hash matches the queried bytes. Email/policy text is inert data,
parsed with safe YAML and no model/code execution. Escaping source symlinks are
rejected. `sources/generated/` is never written by application code.

## Checks

Use `make typecheck`; focused tests are `test_ontology.py`, `test_mappings.py`,
`test_ingestion.py`, `test_resolution.py`, `test_snapshots.py`, and
`test_version_audit.py`. Integration tests require real Postgres/Docker and do
not skip connection failures. Each creates/drops an isolated test schema.

The full suite (`make test`) also runs ticket-01's destructive scratch-volume
reset test. Do not run against data you want to keep. Ticket-01 seed assertions
run the same seed script and Makefile in `.tmp/source-regression/`, preserving
real `sources/generated/` inputs. No tests should run concurrently with a seed
rebuild or the Docker reset test.
