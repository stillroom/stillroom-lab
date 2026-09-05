# 04 — Proof-carrying answers + artifact generation

Status: open
Blocked by: 03
Executor: Astra (manifest schema + template code owned by us)

## Goal

The distinctive experiment: every answer and generated artifact carries a complete
proof manifest, and artifacts are generated only into the output workspace.

## Work

1. Proof manifest fields (per spec): source IDs, retrieval time, snapshot ID,
   ontology/mapping version, approved query, metric definition reference, permission
   context, unresolved conflicts list.
2. Manifest attached to every query response; unresolved conflicts surface, never
   silently dropped.
3. Artifact generation from validated result objects:
   - `openpyxl` spreadsheet template: populated cells + a sources sheet (source IDs,
     caveats, retrieval time).
   - `python-pptx` deck template: populated slides + evidence notes.
   - Short Markdown briefing with inline source references.
4. Output discipline: artifacts write ONLY to `output-workspace/` (single writable
   area). A test asserts generation attempts targeting any other path fail.
5. Absence semantics: "no payment record found" is reported with completeness-check
   status, not as proof of nonpayment (test the wording/logic path).
6. pytest: manifest completeness on every artifact, output-path containment,
   conflict surfacing, absence wording.

## Acceptance criteria

- The case #1 artifact set (spreadsheet + briefing for overdue invoices + unresolved
  tickets) carries complete manifests that trace back to source IDs and snapshot IDs.
- Artifact written outside output-workspace → hard failure (test-verified).
- Every manifest field present on every artifact (schema-validated in tests).
- A query with an unresolved conflict returns the conflict in the manifest (e.g.
  refund vs invoice-date conflict from the seed battery).

## Non-goals

- No sending artifacts anywhere (approval-controlled capability, out of v0). No UI
  (05). No new metrics.