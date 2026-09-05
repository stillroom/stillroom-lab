# 07 — Executor engagement: Astra (protocol)

Status: engaged 2026-09-06 (Adam's go given in chat)
Type: engagement protocol — not a build ticket

## Goal

Define how Astra engages on the build now that Adam has said implement. This ticket
has no code deliverable; it is satisfied by following the protocol.

## Preconditions — status

- [x] Adam says "implement" — given 2026-09-06 in chat.
- [x] Pre-work artefact complete: spec.md (D1–D8), map.md, tickets 01–06.
- [x] Access verification — satisfied by the Astra session itself running. If a
      session cannot start, that IS the verification failing: stop and report to
      Adam; do not retry loops or reconfigure accounts.
- Benchmark (ticket 06) deliberately EXCLUDED from Astra's scope: measurement design
  is Hermes+Adam-owned. Astra never grades its own work.

## Protocol (per ticket, 01–05)

1. One `/implement` run per ticket; fresh context between tickets (/clear).
2. Read only `spec.md` + the ticket file + code under change. The vault research doc
   is out of scope. Token cost guard: $10/$50 per M tokens (cached input $1; >272K
   input $20/$75) — reads are targeted, not exploratory.
3. `/tdd` at the seams the ticket names; tests implement the ticket's acceptance
   criteria exactly, assert real behaviour, no tautologies.
4. Deterministic core (SQL/Decimal, mapping validation, permission checks)
   implemented to spec; any deviation flagged in the diff summary.
5. Full test suite once at ticket end; then `/code-review`; then diff summary +
   proposed commit message; commit only on Adam's approval.
6. Checkpoint with Adam between tickets. Recommended Hermes durable-review
   checkpoints: after ticket 02 (ontology/mapping) and ticket 03 (governed query) —
   the trust-critical cores — and at the end.
7. Token usage logged per ticket for the cost ledger.

## Non-goals

- No Astra involvement in ticket 06. No source-system writes. No commits without
  Adam's approval. No scope beyond the named ticket per run.