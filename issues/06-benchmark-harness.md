# 06 — Benchmark harness

Status: open
Blocked by: 02, 03 (04/05 measured where relevant)
Executor: Hermes + Adam (measurement design owned by us; factual correctness is the
experiment — this ticket is deliberately NOT Astra's)

## Goal

Measure the Lab doc's question instead of asserting it. Independently specified cases
with independently computed expected results; comparative measurement across three
answer modes on identical inputs.

## Work

1. Case set (spec D5, confirmed):
   - Case #1: overdue invoices + unresolved tickets → spreadsheet + briefing with
     source references.
   - First-class: multi-client isolation (zero cross-client leakage under every seed
     trap).
   - Messiness battery: duplicates, missing IDs, partial payments, refunds,
     conflicting dates, stale snapshots, ambiguous metric terms, access restrictions,
     injected instructions.
2. Expected results computed independently (hand-verified spreadsheet/calculations,
   NOT derived from the system under test; stored in `benchmark/expected/`).
3. Three answer modes on identical cases:
   a. manual collation (human baseline, timed),
   b. document-only retrieval (naive RAG-style),
   c. governed semantic querying (the lab's path).
4. Metrics per the doc: numeric correctness, joins, source coverage, appropriate
   abstention, leakage, artifact consistency, latency, source-write prevention.
5. Model benchmark piggyback: tool-calling + JSON reliability measured for the
   explicitly selected Ollama Cloud model. Token usage is read from the audit table
   (per-call logging from ticket 03). No local-model contestant is planned for v0.
6. Results published as a table in `benchmark/RESULTS.md`; no comparative
   superiority claim beyond what the table shows.

## Acceptance criteria

- Every case runs against every mode with a recorded result row.
- Expected-results files show derivation notes (how each expected was computed) and
  differ from system output formats (proving independence).
- Appropriate-abstention cases (absence-of-payment, access-restricted) score correct
  refusal, not hallucinated answers.
- Leakage metric = 0 across the isolation battery for mode (c).
- RESULTS.md states measurement date, seed, provider, versions per row.

## Non-goals

- No optimisation during measurement. No tuning to the cases (they are fixed before
  the run). No claims beyond measured rows.