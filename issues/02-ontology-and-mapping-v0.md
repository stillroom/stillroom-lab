# 02 — Ontology + mapping v0

Status: complete (1a7f1ab)
Blocked by: 01
Executor: Astra (validation logic + tests owned by us)

## Goal

Versioned YAML ontology, ingestion into Postgres, mapping validation with an approval
gate, and the provenance/snapshot backbone. This is the layer every later ticket
depends on — the "written once for reuse" artefact (spec D8).

## Work

1. `ontology/v0.1.0.yaml`: entities Customer, Account, Invoice, Payment, Opportunity,
   Ticket, Communication, Policy; explicit relationships; metric definitions that
   distinguish revenue, cash received, pipeline, overdue balances. Separate
   ontology (meaning) from mapping (source correspondence) from semantic query layer
   (approved metrics + joins).
2. Mapping contracts per source (CRM SQLite, invoice/payment CSVs, support JSON,
   email text, policy Markdown): field-level source→canonical correspondence.
3. Ingestion service (FastAPI + Pydantic): load sources into canonical entities with
   provenance (source ID, retrieval time, snapshot ID) and mapping versions.
4. Entity resolution: candidates proposed, never auto-merged; ambiguous customer
   merges rejected (recorded, surfaced for approval).
5. Approval gate: AI-proposed mappings require explicit approval before promotion to
   trusted; store approval state + who/when.
6. Snapshot mechanism so stale-snapshot cases are representable and detectable.
7. pytest: deterministic fixtures; independently computed expecteds for mapping
   validation, provenance completeness, merge rejection, approval gate.

## Acceptance criteria

- YAML validates against a schema; version is pinned and changes are auditable.
- Ingestion of all five sources produces provenance-complete canonical entities.
- A duplicate-name case produces a resolution candidate, not a silent merge.
- An unapproved proposed mapping cannot be used by any trusted path (test-verified).
- A stale snapshot is detectable via snapshot metadata (test-verified).

## Non-goals

- No query API yet (03). No metrics computation beyond definitions. No AGE/pgvector.