# Governed query API v0.1.0

Local operator-only FastAPI app factory: `create_app(application)` retains the existing
`POST /ingestions` and adds `POST /queries`. No authentication system is provided:
permission context is a mock, not an identity assertion suitable for network exposure.

Example request:

```json
{"approved_query":"v0.1.0/cash_received","permission":{"role":"owner","client_id":"CLIENT-1"},"as_of":"2026-09-01","period_start":"2026-08-01"}
```

Approved references: `v0.1.0/revenue`, `v0.1.0/cash_received`, `v0.1.0/pipeline`,
`v0.1.0/overdue_balances`. The versioned catalog under `ontology/` references the
pinned ontology metrics and joins. Arbitrary SQL or natural-language questions are
not accepted. Cash receipt dates include both period endpoints; omitted period_start
means all observed receipts through as_of. Only cash accepts period_start. Overdue
uses due_at strictly before as_of and payments through as_of, per invoice, flooring
credit balances at zero rather than offsetting another invoice's overdue balance.

Owner may act for CLIENT-1/2/3; analyst for CLIENT-1/2; all other contexts deny.
CLIENT IDs are Account identifiers, not Customer IDs. Role/client checks precede
opening any retrieval connection. Customer access metadata is also filtered in SQL.
Names, email contents, support dates, and policy text cannot override these rules.

Responses contain query_id, snapshot_id, structured reason, and rows. Money is
Postgres numeric -> strict Decimal -> JSON decimal string, never a float. Seed
observations for CLIENT-1 are cash 300.00 and overdue 700.00. CLIENT-2/3 have observed
0.00. All have amount=null: ledger completeness and billing-date authority have not
been established. Revenue and pipeline abstain with empty rows because the ontology
has no delivery/recognition or stage evidence. No complete totals are claimed.

Every query attempt is audited: accepted, denied (403), unapproved (422), invalid
period (422), and failed retrieval/invalid result (503). The audit stores context,
outcome, retrieval_started, row_count, as_of/period_start, ontology/mapping versions,
and zero input/output tokens. Request bodies that cannot form a QueryRequest receive
an audited invalid_request (422), with null dates and no retrieval. Other endpoints
retain their existing FastAPI validation behavior.

snapshot_id identifies a per-call snapshot bundle persisted IN the query_audit row;
it is not a fabricated source snapshot. Its snapshots array records actual source
snapshot IDs, versions, digests, observed and retrieval dates. Authorized queries
capture this bundle and retrieve records in the same repeatable-read transaction.
Denied/rejected queries have an empty bundle and no mapping versions because no
retrieval occurred. The running API sees subsequent committed ingestions. Repeated
observations of the same entity/source ID use the latest retrieved record. Historical
ownership changes, source IDs mapping to multiple canonical IDs, or multiple source IDs sharing a financial identity cause global
metric abstention: without tenant-qualified inherited references, no client can
safely receive numbers. This conservative choice may suppress unrelated clients.
Missing invoice customer IDs remain unresolved and excluded. Source snapshot age and
coverage are evidence, not automatically promoted to current business truth.

The app factory provisions scratch roles using the existing operator Store; it does
not pass that Store into QueryService. Retrieval uses only lab_query (SELECT grants,
read-only default and explicit read-only transactions). Audit uses lab_query_audit
(INSERT only). The ingestion capability remains operator-controlled and writable,
as required by ticket 02; it is not the query credential. Credentials are fixed
scratch-local values for loopback Postgres only. Do not deploy this app or these
credentials. Audit persistence failures prevent returning a query result.

Tests: `uv run --frozen pytest tests/test_queries.py tests/test_query_isolation.py`.
Use the project's Makefile UV_CACHE_DIR/TMPDIR settings. Tests use disposable real
Postgres schemas and do not regenerate or modify source files. No model calls,
artifact generation, agent tools, UI, source writes, or ticket-06 benchmark claims.
