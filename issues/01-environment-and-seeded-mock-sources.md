# 01 — Environment + seeded mock sources

Status: complete (fb2a761)
Blocked by: none
Executor: Astra (deterministic seed scripts + fixtures owned by us)

## Goal

Stand up the lab skeleton: Docker Compose with Postgres only, project scaffolding per
spec.md's repository layout, and the five v0 mock sources seeded with Faker plus
deliberate conflicts. Everything reproducible from a clean checkout with one command.

## Work

1. `docker-compose.yml`: Postgres (pg15 image family, matching the honcho precedent),
   isolated scratch volumes, no public port binding beyond localhost.
2. Project scaffold: `sources/ services/ ui/ agent/ benchmark/ ontology/
   output-workspace/` directories with README stubs.
3. Seed scripts (Python + Faker, deterministic seed) for:
   - CRM SQLite database (customers, opportunities)
   - invoice/payment CSVs
   - support tickets JSON
   - email text corpus
   - policy Markdown, **shaped like vault files** (frontmatter conventions,
     wiki-links) so mapping contracts transfer to real Obsidian ingestion unchanged.
4. Deliberate messiness baked in (the doc's battery): duplicate names, missing IDs,
   partial payments, refunds, conflicting dates, stale snapshots, ambiguous metric
   terms (e.g. "revenue" used loosely), access-restricted records, and at least one
   email containing injected instructions (to test untrusted-data handling later).
5. `make seed` / single script entry point that rebuilds sources from scratch.

## Acceptance criteria

- `docker compose up -d` brings up Postgres; `docker compose down -v` resets it.
- Seed run is deterministic: two consecutive runs produce identical data (fixed seed).
- Every messiness item is present and locatable (each documented in
  `sources/MESSINESS.md` with file + record pointer).
- Policy Markdown files parse with frontmatter and contain wiki-links.
- Injected-instruction email exists and is flagged in MESSINESS.md as a test case.

## Non-goals

- No ontology tables yet (ticket 02). No AGE/pgvector extensions. No services code.