# Ticket 04 validation — 2026-09-08

## Scope

Proof manifests on governed query responses and Markdown, XLSX and PPTX artifacts.
Follow-up corrections address the independent review's two findings:

- Derive manifest mapping versions from selected approved snapshots, sharing the
  same inventory with the audit rather than inferring versions from evidence rows.
- Independently validate permission context for malformed requests, preserving
  valid context despite unrelated errors without granting authorization.

## Executed regression evidence

Before the mapping fix, four real-Postgres HTTP regression cases failed with
`mapping_versions=[]`: revenue, pipeline, financial identity abstention, and
retrieval failure after snapshot selection. After the fix all four passed and
matched the audit's independently asserted five-family inventory.

Before the permission fix, valid permission plus malformed date failed with null
manifest permission. Four invalid/null-context controls already passed. After
independent permission validation, all five cases passed with no retrieval.

## Final gates

- `uv run --frozen pytest tests/test_proof.py -q`: 29 passed.
- `make test`: 66 passed in 53.18 seconds.
- `make typecheck`: no issues in 27 source files.
- `git diff --check`: clean.
- `uv lock --check`: passed.
- Independent follow-up review (`deleg_4648e1f1`, 2026-09-08): passed;
  no security concerns, logic errors or suggestions for the two corrections.
  Reviewer inspected the staged code and new regression tests; no DB tests rerun.
- Added-line static scan: no matching hardcoded-secret, shell injection,
  unsafe deserialization, eval, or interpolated execute patterns.

Two existing warnings remain: Starlette/AnyIO deprecation and the deliberate
Pydantic float-injection rejection test. Neither is a test failure.

The earlier independent review is retained at
`/home/hermes/.hermes/reports/sol-review-ticket04-20260908.md`; its residual
robustness suggestions are not all implemented. No new metrics, UI, source-system
writes, artifact sending or ticket-06 benchmark claims are included.
