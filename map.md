---
created: 2026-09-06
feature: Stillroom Lab v0
spec: spec.md
---

# Stillroom Lab v0 — Map

## Notes

- Research record: `/home/hermes/Documents/life-os/Business/Stillroom/business-brain/Stillroom Lab — Prototype Architecture.md` (authoritative for rationale + sources).
- Build root: `/home/hermes/Projects/stillroom-lab/` (Adam's directive: self-contained folder).
- Host decision: this PC (D1). SSH/GPU machine is stage 2.
- Executor: Astra, gated on Adam's explicit go (D4). Everything before ticket 07 is
  pre-work quality.

## Decisions-so-far

- D1–D8 recorded in spec.md (host, Postgres, dbt deferral, executor split, benchmark
  set, front-end deferral, model config switch, Stillroom-shaped mocks). Confirmed by
  Adam 2026-09-06 in the Phase A interview.

## Fog

- Which explicitly selected Ollama Cloud model is reliable enough across the fixed
  Ticket 06 cases; measured rather than assumed.
- Whether the governed-query layer stays a thin module under load (second-pass lab
  question, deferred).