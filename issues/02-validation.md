# Ticket 02 — execution evidence

Baseline: `fb2a761ee59c432e5686e9d1836c28f907c161dd`.
Implementation scope: ticket 02 only. No commit created.

## Method and boundaries

Read `spec.md`, then `issues/02-ontology-and-mapping-v0.md`. Used the
`implement`, `tdd`, and `code-review` workflows. Public seams were supplied by
Adam: ontology loader, mapping validation/approval, ingestion application/HTTP
and store inspection, entity-resolution candidates, snapshot freshness.

Worked in vertical slices, running the new failing acceptance test before its
implementation and rerunning its focused file. Initial red runs included missing
public modules, rejection of invalid ontology data, unimplemented approved
ingestion, missing snapshot/candidate/audit inspection, and rejecting name-based
identity mappings. One intermediate mypy failure (`object` passed as canonical
ID) was corrected with explicit string validation; subsequent typechecks passed.
No acceptance criterion was removed or weakened.

The original ticket-01 seed assertions rebuild an isolated copy of the same
Makefile/seed script in `.tmp/source-regression/`, not the actual ingestion
inputs. The real Docker regression still targets this repository's Compose
project. The seed script, Compose file, messiness and policy assertions are
unchanged from the baseline.

## Checks before review

All focused commands use `UV_CACHE_DIR=$PWD/.cache/uv`, `TMPDIR=$PWD/.tmp`,
and `uv run --frozen pytest <file> -q`:

- `tests/test_ontology.py`: 2 passed.
- `tests/test_mappings.py`: 3 passed; all five families blocked via application
  and HTTP while proposed; named approval persisted and read back.
- `tests/test_ingestion.py`: 1 passed; all five actual source families, 17
  observations with provenance, typed facts, inert injected text, unchanged bytes.
- `tests/test_resolution.py`: 1 passed; distinct customers, pending candidate,
  audited denied merge, persisted rejection, no rejection reset on re-ingestion.
- `tests/test_snapshots.py`: 1 passed; T001 fresh/T002 stale at 2026-09-01,
  explicit 30-day threshold and boundary assertion.
- `tests/test_version_audit.py`: 1 passed; persisted version/digest/timestamp,
  changed same-version ontology/mapping rejected without overwriting approval.
- `tests/test_seed.py`, `tests/test_messiness.py`, `tests/test_policies.py`:
  each 1 passed in separate focused runs.
- `make typecheck`: success, no issues in 20 source files (run regularly).
- `git diff --check`: passed after removing trailing blank lines.

### Single full-suite final test gate

`make test` was run **exactly once**: **13 passed, 1 warning in 11.81s**.
All four ticket-01 tests passed, including the real Postgres localhost binding,
volume reset and fresh-database checks. Warning: Starlette TestClient imports the
deprecated `anyio.abc.BlockingPortal` alias; no test failures/skips.

After the suite, all 8 generated source files had identical SHA-256 values to
before the suite. Postgres was healthy at `127.0.0.1:55432`; no test schemas or
production `stillroom_v02` schema remained. Test-only approval records were
removed with their schemas; checked-in mapping contracts remain proposed.

## Review

Two read-only axes dispatched against `git diff fb2a761 --`, including new files
via intent-to-add. No commits exist after the fixed baseline. The normal
three-dot HEAD diff would miss this uncommitted implementation.

No repository coding-standards file or `docs/agents/issue-tracker.md` exists;
review uses the supplied local spec/ticket and the skill's smell baseline.

### Spec axis (completed): no blockers found

All acceptance features present with no ticket-03+ scope. Nonblocking finding:
`validate_mapping()` did not enforce source-family completeness — an incomplete
future contract (e.g. billing without payments) could validate, be approved and
ingest. Resolution: `MappingContract.complete_family` now requires every dataset
of the family (CRM customers+opportunities; billing invoices+payments; support
tickets; email messages; policy documents) with a new red→green rejection
assertion in `tests/test_mappings.py`. Affected checks rerun green
(`tests/test_mappings.py tests/test_ingestion.py`: 4 passed; `make typecheck`:
clean, 20 files; `git diff --check`: clean).

### Standards axis (completed inline, by executor): deviation recorded

The standards subagent could not run: its model provider (`gpt-5.6-sol`, OpenAI
Codex) returned `HTTP 429: The usage limit has been reached` after retries, and
OpenAI access is unavailable until ~12:15 AEST. With Adam's approval the
executor ran the standards axis inline instead of delegating it. Deviation:
the two axes were not executed in isolated subagent contexts; the spec axis was
subagent-run, the standards axis was executor-run against the same fixed diff.

Findings and resolutions (no repo standards file exists; smell baseline applied):

- **Duplicated Code** (judgement): `complete_family` restated the family→dataset
  map that `SOURCE_FIELDS` already owns. Fixed — it now derives required datasets
  from `SOURCE_FIELDS` directly, so the adapter field registry is the single
  source of dataset truth.
- **Mysterious Name / dead constant** (judgement): `PINNED_VERSION` in
  `services/ontology.py` was referenced nowhere. Removed; the ontology pins its
  version via the `Ontology.version` literal, which the schema.sql CHECK and the
  audit test enforce.
- **Primitive Obsession** (judgement, accepted): `family`/`version` travel as
  strings keyed by DB uniqueness; a value object would add a layer the v0 store
  does not need. Accepted as-is for v0.
- **Long method** (`Application.ingest`, judgement, accepted): per-record loop is
  explicit about snapshot/record insertion order; splitting it would hide the
  transactional shape. Deferred to review-driven refactor if tickets 03+ grow it.
- No hard defects found: no invented SQL from source data, no source writes,
  secrets limited to the ticket-01 public sandbox DSN, no unvalidated YAML
  execution, no ticket-03+ scope.

### Review-gate status

Spec axis: clean (no blockers), one nonblocking finding fixed and re-verified.
Standards axis: findings above addressed or explicitly accepted; checks rerun
after fixes: focused tests 9 passed (`test_ontology`, `test_mappings`,
`test_ingestion`, `test_resolution`, `test_snapshots`, `test_version_audit`),
`make typecheck` clean (20 files), `git diff --check` clean. Full-suite count
remains the single earlier `make test` run (13 passed); no full-suite rerun was
performed, matching the one-final-gate instruction.
