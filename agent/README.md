# Single governed agent

`runner.Agent` makes one bounded OpenAI-compatible completion. The model proposes
one `governed_query` and (only when the caller explicitly enables formats) local
`generate_artifact` calls. The entire proposal is validated before execution.
No SQL, shell, arbitrary path, source-write, ingestion, or sending tool exists.
The query schema comes from `QueryRequest`, narrowed to the current query catalog.
Caller-supplied permission and dates cannot be changed by the model.

Facts, Decimal values and the complete proof come only from `QueryService`.
Model prose is discarded; deterministic briefing text is displayed literally.
There is no second model turn after retrieval, so corpus content cannot create
additional calls. The proof object is passed through, not regenerated.
Ambiguous/no-tool proposals are rejected rather than narrated as answers.

The advertised schema inlines the permission object for transport compatibility;
JSON-string permissions remain invalid. Metric guidance explains the evidence
already returned by the catalog, including customer-level overdue observations and
unresolved-ticket sources. It does not promise confirmed invoice-level balances.
Tool choice is `auto` so the model can abstain; validation still requires exactly
one governed query before any execution. The application supplies authoritative
permission/date context, not an example for the user to replace.

## Provider selection (no automatic fallback)

- Unset `STILLROOM_PROVIDER` or `disabled`: clear error, no client/network call.
- `openai`: explicit cloud opt-in; also requires `STILLROOM_MODEL` and
  `OPENAI_API_KEY`. Endpoint is fixed to `https://api.openai.com/v1`.
- `ollama-cloud`: explicit cloud opt-in; requires `STILLROOM_MODEL`.
  Endpoint is fixed to `http://127.0.0.1:11434/v1`; Ollama must already be configured.
- `ollama-local`: deliberately disabled pending locality verification. Loopback
  alone does not prove local inference. No model-name heuristic grants cloud access.

One OpenAI Python SDK client, 30-second timeout, zero retries. No inferred model,
custom endpoint, credential discovery, or fallback. Questions and caller context
are sent only after opt-in; retrieved records are never sent. Tests use the real
SDK with a **scripted transport**, not a live provider or evidence of model quality.
A separate authorised three-case live smoke test with `glm-5.3-flash:cloud`
passed normal, ambiguity and injection checks on synthetic isolated data; see
`issues/05-validation.md`. This is not a model-reliability benchmark.

## Python use (operator-provisioned store required)

```python
from datetime import date
from agent.provider import provider_from_env
from agent.runner import Agent
from services.query import PermissionContext, QueryService

provider = provider_from_env()  # explicit opt-in required
try:
    answer = Agent(QueryService("stillroom_v02"), provider).answer(
        "Which overdue invoices have unresolved tickets? Produce a briefing and spreadsheet.",
        PermissionContext(role="owner", client_id="CLIENT-1"),
        as_of=date(2026, 9, 1), artifact_formats=("md", "xlsx"),
    )
    print(answer.text)
    print(answer.artifacts)
finally:
    provider.client.close()
```

Artifact tools accept only a format and use the current governed result, never
model-provided facts or paths. Caller-enabled formats grant capability, not a
promise the model will request every format. Files have generated UUID names and
cannot overwrite. Denied/failed queries never generate artifacts.

Reported provider token usage is validated directly from raw response JSON before
SDK coercion: both counts must be genuine non-negative integers within PostgreSQL's
integer range. Those exact validated values are written to the existing query audit
for executed queries and rejected proposals. Deterministic callers retain zero
counts. Transport failures/missing or malformed usage do not invent counts and
execute no tool; no cost estimate or live inference benchmark is asserted here.
