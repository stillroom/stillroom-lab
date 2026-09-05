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

- Whether Astra account access actually works from this machine (unverified; gated).
- Whether `qwen2.5:4b` tool-calling/JSON reliability clears the bar (stage-2 benchmark
  contestant; cloud-first until measured).
- Whether the governed-query layer stays a thin module under load (second-pass lab
  question, deferred).