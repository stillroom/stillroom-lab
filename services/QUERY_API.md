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

Responses contain query_id, snapshot_id, structured reason, rows, and a required proof manifest. Money is
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
Ticket 04 acceptance: `uv run --frozen pytest tests/test_proof.py`.
Use the project's Makefile UV_CACHE_DIR/TMPDIR settings. Tests use disposable real
Postgres schemas and do not regenerate or modify source files. No model calls,
agent tools, UI, source writes, or ticket-06 benchmark claims.

## Proof-carrying artifacts (ticket 04)

`services.artifacts.generate(result, Path(...))` accepts a typed `QueryResult` from
`QueryService.execute`. It revalidates nested types, snapshot identity, source
coverage, retained source conflicts and row/client context before writing. This is
an internal Python boundary, not a new HTTP endpoint or an authenticity signature;
callers must obtain results from the governed service, not a model-authored payload.

Extensions `.xlsx`, `.pptx`, and `.md` select the template. Paths must be inside the
fixed repository `output-workspace/`. Parent traversal, symlink directories/files,
and existing destinations (including hard links) fail; no overwrite capability is
provided. Linux directory-relative opens use O_NOFOLLOW/O_EXCL. Output-workspace
and repository ancestors are operator-controlled; hostile concurrent directory
renaming or mount manipulation by the operator is outside this local sandbox.

Every response, including denial, invalid input and failure, has all manifest
fields. Approved-query and metric references are null for unapproved/malformed
requests; malformed or absent permission context is null. A separately validated
permission context survives unrelated request validation errors; this records
submitted context, not an authorization grant. Empty evidence is explicit, not
invented provenance. `retrieved_at` is query-envelope creation time in UTC; each
`sources` entry separately retains ingestion retrieval time and source observation
date, source snapshot ID, family and mapping/ontology versions. `snapshot_id`
remains the audited per-call bundle identifier. Manifest sources are permission-
scoped observations supporting the answer (including support conflicts), not a
claim that every listed observation contributed to a numeric sum. Audit snapshots
retain ticket 03's full approved-snapshot inventory unchanged. Manifest
`mapping_versions` records that selected inventory independently of evidence rows,
including approved abstentions and failures after snapshot selection. It stays
empty when no snapshots were selected (including failures before selection),
without inventing mapping context.

Support is selected by the same authorized Customer scope, with historical Ticket
identity ambiguity checked before latest-row selection. Unresolved tickets are
those whose observed status is neither `closed` nor `resolved`; these are source
observations, not assertions of present-day status. Support dates never change
billing arithmetic. Conflicting billing/support dates carry both source references.
Financial/support identity ambiguity and unattributed invoices surface as generic
conflicts without leaking the unscoped record IDs. Unavailable revenue/pipeline
metrics retain their explicit abstention, without supporting record retrieval.

Completeness remains `not_established`: no completeness authority exists in v0.
An invoice with no observed payment through as_of says "no payment record found"
and "not proof of nonpayment" alongside that status. This check ignores a cash
period's lower bound, so a receipt outside the requested period is not falsely
called missing. Confirmed monetary amounts remain null.

The workbook has Results, Tickets, Sources and Manifest sheets; the complete JSON
manifest is chunked across Manifest column A to avoid Excel cell truncation. Money
is exact Decimal text, deliberately not Excel numeric cells or formulas. Oversized
source cells fail instead of silently truncating. Retrieved text is forced to
string cells, never executable formulas. The deck has populated slides and the
full JSON manifest in every slide's notes. The Markdown briefing has inline source
footnotes and a fenced JSON manifest. Artifacts do not perform arithmetic, retrieve
sources, send content, or change business records.
