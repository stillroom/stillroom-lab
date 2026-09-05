# 03 — Governed query API

Status: open
Blocked by: 02
Executor: Astra (SQL/Decimal correctness, permission checks, tests owned by us)

## Goal

The read-only query surface: allowlisted approved queries, Decimal-safe arithmetic,
server-side permission enforcement before retrieval, and the query audit trail with
per-call token logging.

## Work

1. Semantic query layer: approved queries derived from ontology metrics + joins; a
   query not in the allowlist is rejected with a structured reason.
2. All money math in SQL/Decimal. Models never calculate (this is a hard rule; a test
   asserts the API layer's arithmetic never touches a float path for money).
3. Permission context per query (mock roles/clients): enforced **before** retrieval —
   denied queries produce no rows and an audit entry, never a redacted result set.
4. Multi-client isolation at the query layer: a query acting for client A can never
   surface client B records (first-class benchmark case from spec D5).
5. Query audit trail: query ID, approved-query reference, permission context,
   snapshot ID, ontology/mapping versions, row counts, per-call token usage (model
   calls logged alongside; zero tokens for pure deterministic queries).
6. Read-only enforcement: API service connects with read-only Postgres credentials;
   a test proves writes fail at the DB layer.
7. pytest: independently computed expecteds for the metric definitions (revenue vs
   cash received vs pipeline vs overdue), permission denials, isolation, allowlist
   rejection, audit completeness.

## Acceptance criteria

- A metric question ("overdue balances by customer") returns Decimal-exact results
  matching the independently computed expected file.
- Permission denial happens pre-retrieval: audit shows denial, no row access
  (test-verified via audit inspection).
- Cross-client leakage test: query for client A returns zero client B rows under
  every seed scenario, including shared-name and shared-ID traps.
- Non-allowlisted query rejected with structured reason (test-verified).
- Audit trail rows exist for every query; token column populated.

## Non-goals

- No artifact generation (04). No agent/UI (05). No natural-language parsing of
  arbitrary questions — the agent layer proposes; this layer disposes.