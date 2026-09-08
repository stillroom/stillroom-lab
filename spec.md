---
created: 2026-09-06
owner: Adam
status: v0-in-progress (tickets 01–05 = Astra; 06 benchmark = Hermes+Adam; 07 = protocol)
executor: astra-engaged-2026-09-06 (Adam's go; one /implement run per ticket, protocol in issues/07; benchmark ticket 06 stays Hermes+Adam-owned)
related:
  - "[[Stillroom Lab — Prototype Architecture]]"
---

# Stillroom Lab v0 — Build Spec

Self-contained build root: `/home/hermes/Projects/stillroom-lab/` (Adam's directive,
2026-09-06). Research record stays in the vault; this spec and all build artefacts live
in the project directory. This spec is the "pre-work artefact" the Lab doc requires.

## Goal

Prove or kill the question in the Lab doc: **can a small explicit business ontology
plus governed deterministic queries answer cross-system questions and produce
source-traceable artifacts without writing to source systems?** Measured on the v0
benchmark set — not asserted.

## Non-goals (v0)

- No writes to any source system (v0 mocks are files; artifact writes go to the output
  workspace only).
- No Kafka, no separate graph cluster, no swarm, no fine-tuning, no full OWL reasoner.
- No multi-user auth system; permissions are per-query context, enforced server-side.
- No hosted/managed deployment; everything runs on this PC.
- No comparative superiority claims in any output until the benchmark harness measures
  them.
- No dbt-core (evaluated, deferred — verification gate is pytest + SQL checks we own).

## Decisions locked (from research + Phase A interview, 2026-09-06)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Host = this PC | Docker proven here (honcho stack); zero SSH dependency. SSH/Tailscale is a stage-2 item when the GPU PC joins for local-model inference. |
| D2 | Primary datastore = Postgres | Matches running honcho-database pgvector:pg15. pgvector + Apache AGE cover embeddings and graph later in one engine. Neo4j Community lacks row-level security (Enterprise-only). |
| D3 | dbt-core deferred; verification gate = pytest + SQL | dbt's SQL/Jinja model shape conflicts with the ontology/mapping/governed-query core. |
| D4 | Executor split | Astra executes build tickets ($10/$50 per M tokens — deterministic core must carry bulk work); deterministic core (SQL/Decimal, mapping validation, permission checks) + tests stay owned by us; every ticket gets /code-review before done. **Astra not engaged until Adam says implement.** |
| D5 | Benchmark set confirmed | Case #1: overdue invoices + unresolved tickets → spreadsheet + briefing with source references. First-class case: multi-client isolation. Plus the messiness battery: duplicate names, missing IDs, partial payments, refunds, conflicting dates, stale snapshots, ambiguous metric terms, access restrictions, injected instructions in emails. |
| D6 | Front end deferrable | Streamlit first (fast prototype), Dash if client-facing polish is needed later. Same data layer either way; swap cost low. |
| D7 | Model strategy is a config switch | One OpenAI-compatible client uses explicitly selected Ollama Cloud models through `127.0.0.1:11434/v1`. Model changes remain environment-variable configuration; no local-model contestant is planned for v0. |
| D8 | Mock business mirrors Stillroom | Lab sources model a one-person consultancy; ontology/mapping/metric/permission artefacts written once for reuse at stage 2 (Stillroom = client #1). Vault-shaped document mocks so mapping contracts transfer to real Obsidian ingestion unchanged. |

## Architecture (one sentence per layer)

- **Sources (mock):** CRM database (SQLite), invoice/payment CSVs, support JSON,
  email text, policy Markdown (vault-shaped) — seeded with Faker + deliberate
  conflicts. Later sources (content pipeline, website, time tracking, proposals/
  contracts, scheduling, knowledge library, credentials, subscriptions,
  onboarding/offboarding) enter as the next entity sets — confirmed in: time tracking,
  proposals, contracts.
- **Canonical store:** Postgres (Docker, scratch volumes) — entities, source mappings,
  typed facts, provenance, mapping versions, snapshots, query audit trail.
- **Ontology:** versioned YAML — Customer, Account, Invoice, Payment, Opportunity,
  Ticket, Communication, Policy; explicit relationships + metric definitions.
  Ontology (meaning) ≠ mapping (source correspondence) ≠ semantic query layer
  (approved metrics and joins).
- **Services:** Python FastAPI + Pydantic — ingestion, mapping validation, entity
  resolution candidates, governed query API. All arithmetic in SQL/Decimal. Models
  never calculate.
- **Verification gate:** pytest with deterministic fixtures and independently
  computed expected results. Factual correctness is the experiment.
- **UI:** Streamlit, read-only, proof drawer.
- **Agent:** one agent, typed tools, plain Vercel AI SDK initially; eve optional after
  testing. Cloud inference is explicit opt-in, never an invisible fallback.

## Proof-carrying answers (the distinctive experiment)

Every factual answer and generated artifact carries a manifest: source IDs, retrieval
time, snapshot ID, mapping/ontology version, approved query, metric definition,
permissions, unresolved conflicts. UI proof drawer traces output to evidence. AI
proposed mappings require approval before promotion to trusted. Ambiguous customer
merges rejected. Revenue ≠ cash received ≠ pipeline ≠ overdue. Absence of a payment
record is not proof of nonpayment without completeness checks.

## Security boundary

Read-only credentials; server-side allowlisted tools; permissions enforced **before
retrieval**, not via prompt or output redaction. Retrieved emails are untrusted data,
never instructions. Source writes out of scope; artifacts write only to the output
workspace. Sending artifacts or changing business records = separate approval-controlled
capability (not in v0).

## Repository layout

```
/home/hermes/Projects/stillroom-lab/
├── spec.md                      ← this file (single source of truth for v0)
├── issues/                      ← tracer-bullet tickets (Phase C output)
├── map.md                       ← wayfinding map (Notes / Decisions-so-far / Fog)
├── ontology/                    ← versioned YAML (v0.1.0)
├── sources/                     ← mock source definitions + seed scripts
├── services/                    ← FastAPI ingestion + governed query API
├── ui/                          ← Streamlit read-only front end
├── agent/                       ← one agent, typed tools
├── benchmark/                   ← cases, fixtures, independently computed expecteds
├── output-workspace/            ← generated artifacts land here (only writable area)
└── docker-compose.yml           ← Postgres (+ AGE/pgvector when earned)
```

## Tickets (tracer-bullet order, blockers-first)

- **01 Environment** (no blockers) — compose file (Postgres only), project
  scaffolding, seed scripts for the five mock sources, vault-shaped doc mocks.
- **02 Ontology + mapping v0** (blocked by 01) — YAML ontology v0.1.0, ingestion,
  mapping validation, approval gate, provenance + snapshot tables.
- **03 Governed query API** (blocked by 02) — allowlisted queries, Decimal math,
  permissions enforced pre-retrieval, audit + per-call token logging.
- **04 Proof-carrying answers** (blocked by 03) — manifest fields, artifact generation
  (openpyxl/python-pptx) to output workspace with source notes + caveats.
- **05 Agent + UI** (blocked by 03) — one agent with typed tools, Streamlit read-only
  front end, proof drawer.
- **06 Benchmark harness** (blocked by 02, 03) — the confirmed case set (D5),
  independent expecteds, measured comparison vs manual collation and document-only
  retrieval: numeric correctness, joins, source coverage, appropriate abstention,
  leakage, artifact consistency, latency, source-write prevention.
- **07 Executor run: Astra** (blocked by 01–06 + Adam's go) — engage Astra on the
  prepared artefact. Blocked by an explicit human decision, not by work.

## Acceptance criteria (the experiment)

1. Benchmark harness runs all confirmed cases green against independently computed
   expecteds — including multi-client isolation and the injected-instruction case.
2. Every benchmark answer/artifact carries a complete proof manifest.
3. Zero source-system writes (verified by test, not by claim).
4. Permission denials happen before retrieval (verified by audit-trail inspection).
5. Model swap = environment-variable change; per-call tokens logged in the audit table.
6. `/code-review` passed on the final diff of every ticket.

## Risks / unknowns

- **Astra access unverified from this machine** (no OPENAI_API_KEY in env; codex config
  has no astra/gpt-6 entries). Gate D4 on Adam's go; verification is part of ticket 07.
- **GPU PC hardware unverified** — out of v0 scope by D1; revisit at stage 2.
- **Multica** stays a research note; plain issue files suffice for v0 orchestration.
- **eve** stays untested; plain agent first.
- **Second-pass enterprise-scale mock** deliberately deferred until after Stillroom
  self-deployment runs.