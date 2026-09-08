# Ticket 05 validation — agent and read-only UI

## Continuation: actual model-to-query path (2026-09-08)

This section supersedes the earlier scripted-only verification limitation below;
the earlier report and review are retained as historical evidence.

- Runtime/test edits confined to `agent/runner.py` and `tests/test_agent.py`.
  No provider, governed-query, permission, proof or SQL implementation changes.
- Red → green: advertised metric evidence was absent; permission was a `$ref`
  rather than an inline object; `required` tool choice contradicted abstention.
  Each request-contract assertion failed before its focused fix. Added negative
  cases confirm JSON-string permissions and extra nested permission fields remain
  rejected before retrieval. No malformed-proposal normalization was added.
- The first continuation live call recognised overdue_balances but mistook the
  context block for an example and safely rejected (569 input / 401 output tokens).
  Preserved in `.tmp/ticket05-live-resume-first-attempt.json`. A failing prompt
  regression preceded explicitly labelling the actual application-supplied
  context; no additional model turn or fallback was introduced.
- Final live smoke: explicit `ollama-cloud` / `glm-5.3-flash:cloud`, three requests,
  one per question. Actual provider counts: normal **612/201**, ambiguous
  **610/419**, injection **677/245** (input/output), exactly matched audit rows.
  Normal and injection returned the expected customer `C001`, client `CLIENT-1`,
  observed `700.00`, confirmed amount unset, `T001` evidence and intact manifest.
  Ambiguity rejected before retrieval. Injection included synthetic seed email
  E002 plus a CLIENT-3/SQL escalation request; no extra tool or artifact executed.
- All non-audit tables in the isolated synthetic schema, source bytes and output
  bytes compared unchanged. Schema deletion verified by reading pg_namespace.
  Parent also parsed the actual normal/injection tool arguments: permission is
  an object, not a repaired string, and each response contains only governed_query.
  The rendered answer's embedded JSON exactly equals the governed manifest.
  Raw requests/responses, results, audit rows and checks:
  `.tmp/ticket05-live-resume-results.json`; reproducible bounded harness:
  `.tmp/live05_resume.py`. Original `.tmp/live05.py` and prior results preserved.
- Full gates: `make test` **115 passed**, two existing warnings, 79.80 seconds;
  `make typecheck` **36 files clean**; `uv lock --check` and `git diff --check`
  passed. Static scan found only fake `test-only` transport keys; scan retained
  in `.tmp/ticket05-resume-security-scan.json`.
- Limit: this proves a narrow question-to-governed-query connection with evidence,
  not general model reliability or a definitive invoice-by-invoice answer. The
  existing governed result is customer-level observed balances plus ticket/source
  evidence, with incompleteness and due-date-authority caveats. No Ticket 06 work,
  source writes, architecture expansion, staging or commit.
- Independent continuation review **passed with no findings**:
  [verdict](05-continuation-review.json), delegation `deleg_3e317bce`.
  Completion metadata reports worker `gpt-5.6-sol`, correcting the parent's
  pre-launch expectation of an inherited controller model. Reviewer independently
  ran 38 agent tests and 44 query/proof tests; its transcript contains the passing
  tool results. Parent independently ran the full 115-test gate above and checked
  raw live arguments, rendered proof equality, schema removal and clean diff/index.
  This is a continuation review, not a claim of a separate full-ticket durable
  checkpoint. Request model `glm-5.3-flash:cloud` returned model label
  `glm-5.3-flash`; provider-side identity/routing is not independently proven.
  Earlier review below predates this delta and remains preserved.

## Earlier scripted-only verification (preserved)

Date: 2026-09-08 (Melbourne). Base: `9548fea`.
Status: implemented, locally verified and independently reviewed; no commit authorized.

Final result: **113 tests passed**, strict mypy **36 files clean**, lock/diff checks
passed. Final independent review: **passed, no findings** ([verdict](05-review.json)).
Pre-existing edits preserved; HEAD remains `9548fea`; nothing staged.

## Implemented boundary

- One OpenAI-compatible Python SDK client, selected only by explicit environment
  opt-in. Unset provider fails before client construction, even with credentials
  present. Explicit OpenAI and loopback Ollama Cloud configurations; local inference
  remains disabled pending model-locality verification. No automatic fallback.
- One model proposal batch, one typed governed query, optional explicitly enabled
  typed artifact requests. Entire proposal validated before execution; model cannot
  change caller permissions/dates, introduce SQL, arbitrary paths or new tools.
- Model prose discarded. Governed Decimal observations, ticket evidence, caveats
  and proof are rendered deterministically. Manifest retained unchanged. Retrieved
  email/source data never enters a subsequent model tool-calling turn.
- UI has question/date inputs, literal answer pane, full JSON proof drawer, and
  permission-bound existing-artifact downloads. No ingestion, operator provisioning
  or artifact-generation UI capability. Sources and business stores remain unchanged.
- Actual reported completion usage is appended to existing query audits, including
  rejected proposals. Pure deterministic queries preserve their zero-token behavior.

## Execution evidence

Baseline before edits: `make typecheck` clean (27 files); existing query suite
15 passed. Pre-existing Starlette/AnyIO deprecation warning observed.

TDD seam evidence:
- Provider tests failed on absent provider module, then 4 passed.
- Case #1 failed on absent runner; then real-Postgres governed query returned the
  independently specified `700.00` observation and `T001`, with intact proof and
  test-provider usage 41 input / 12 output tokens persisted in the audit.
- Explicit spreadsheet/briefing test failed on missing artifact capability; then
  generated actual files and reopened them, comparing the embedded manifest.
- Hostile proposal tests exposed missing rejected-call usage auditing (7 failures);
  fixed with pre-retrieval governed rejection auditing. Injected seed email E002,
  extra/unknown tools, SQL, altered permission/date, extra fields and empty proposals
  cannot expand capabilities or echo model instructions as an answer.
- Download tests failed on absent boundary, then 8 passed: byte equality, permission
  mismatch, traversal/absolute/non-artifact names, and symlink rejection.
- Streamlit AppTest failed on absent application, then 3 passed: default disabled,
  real question → query → rendered complete proof, existing-artifact loading, and
  positive call/import surface scanning. All business-table contents and source/
  output file hashes compared before/after; only one extra query-audit row.

Initial final gates:
- `uv run --frozen pytest -q`: **91 passed**, 2 warnings, 66.10 seconds.
- `make typecheck`: **36 files clean** (agent/UI included).
- `uv lock --check`: resolved 70 packages, lock current.
- Real Streamlit startup using `.venv/bin/python -m streamlit`, loopback port 18505,
  headless and telemetry disabled: `/_stcore/health` = `ok`, `/` = HTTP 200.
  Initial background launch via `uv` failed because that shell lacked `uv` in PATH;
  using the absolute project interpreter succeeded. No production workaround needed.
- Added provider-configuration/error-path checks: fixed endpoints despite ambient
  `OPENAI_BASE_URL`, explicit model/key requirements, no retries, disabled/unknown/
  unverified-local modes, HTTP failure, timeout, missing usage and malformed payload.
  These use no live inference.
- Pre-review-fix consolidated gate: `make test` = **101 passed**, 2 existing warnings,
  69.19 seconds; `make typecheck` = **36 files clean**; lock and diff checks passed.
- Static security scan: 11 changed/new Python files; only hit was the intentionally
  fake `api_key='test-only'` transport fixture. No production secret, shell/eval,
  unsafe pickle or SQL-interpolation pattern hit.

## Review

Fresh-context read-only reviewer: delegation `deleg_9226b759`, child
`sa-0-d4e291d6`. Initial verdict: request changes for a P2 token-usage validation
hole (`agent/runner.py`): negative counts accepted by the SDK could permit retrieval
then fail audit constraints. Parent reproduced both negative and PostgreSQL-integer
overflow counts reaching the execution seam. Narrow fix delegated to fresh context
`deleg_80eda6a7`; parent inspected the actual patch and independently reran all gates:
`make test` **107 passed**, 2 existing warnings, 74.13 seconds; `make typecheck`
**36 files clean**; lock and diff checks passed. The fix rejects negative, fractional
and overflowing prompt/completion counts before both execution and rejection-audit
seams. Follow-up independent review `deleg_c7698f15` found that SDK coercion still
normalizes `true`, `"1"` and `1.0` into integer counts before that guard. Parent
reproduced all six additional cases (both token fields). Second bounded fix context
`deleg_34d9572a` changed the single SDK request to its raw-response interface and
validates raw JSON counts before SDK parsing. Parent inspected the changed code,
then independently ran `make test`: **113 passed**, 2 existing warnings, 78.50 seconds;
`make typecheck`: **36 files clean**; lock and diff checks passed. Final independent
review `deleg_62cfd8d4` **passed with no findings**. Parent read and validated the
actual JSON verdict, now retained as `issues/05-review.json`. Reviewer independently
probed all 12 invalid cases, valid zero/maximum execution and rejection counts, and
exactly one mock request per answer; no live inference was performed. The first
follow-up verdict is preserved in
`.tmp/ticket05-followup-review.json`.

The reviewer inherits the configured controller model; this is not represented as
the separate Sol durable-review checkpoint.

## Deliberate interpretations and unverified scope

1. Python OpenAI SDK instead of the spec's initial Vercel AI SDK: keeps the Python
   governed layer and Streamlit in one runtime, with the same typed boundary.
2. Literal zero writes to *any* store is incompatible with mandatory query auditing.
   UI writes no sources, canonical/configuration tables or artifact files; the
   governed layer still appends query-audit rows. Tests prove this narrower boundary.
3. All inference tests use a scripted HTTP transport through the actual SDK, not a
   live model. No cloud inference was authorized or performed. Live provider/model
   tool reliability remains unverified; benchmark Ticket 06 was not touched.
4. No production auth claim. Operator-provided permission context and existing local
   artifacts are trusted inputs, as in v0. Downloads require matching proof context.
5. Build-session token/cost totals are unavailable in this execution interface and
   are not estimated. Test token values above are fixture values, not build usage.

## Preserved work

No commit or staging operation. Existing edits retained byte-for-byte:
- `.gitignore`: SHA-256 `cf2e9e89d43181a782e8f03b6d5cdb409afcff392da8e20cbe3903f034b6c528`
- `issues/07-executor-run-astra.md`: SHA-256 `926afaae3d272d31fd1f3b9519cce32c2ef7d7b5247336a8cde73e71ca03259a`
