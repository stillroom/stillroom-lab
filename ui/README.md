# Read-only Streamlit UI

Run from the project root (locked environment, loopback only, telemetry disabled):

```sh
uv run --frozen python -m streamlit run ui/app.py \
  --server.address 127.0.0.1 --server.headless true \
  --browser.gatherUsageStats false
```

Open the local URL printed by Streamlit. With no provider environment, pressing
**Ask governed agent** shows a clear disabled-inference error without contacting a
provider or database. See `agent/README.md` for explicit provider opt-in.

The UI never initializes a Store, registers/approves mappings, ingests sources, or
provisions roles. An operator must prepare the store separately using the existing
`services/README.md` workflow and `services.query_storage.provision_queries(store)`.
Settings: `STILLROOM_SCHEMA` (default `stillroom_v02`), `STILLROOM_ROLE` (default
`analyst`), `STILLROOM_CLIENT_ID` (default `CLIENT-1`). These are trusted local
operator context, **not authentication**. Do not expose this prototype publicly.

- Ask a question with an explicit as-of date; optional period start is for cash receipts.
- The answer is literal deterministic text, not model prose or executable Markdown.
- The expandable proof drawer renders the **whole** governed manifest, including
  source IDs/evidence, retrieval times, snapshot, ontology/mapping versions, approved
  query, metric reference, permission context, conflicts, caveats and completeness.
- To download a previously generated artifact, paste its UUID basename. Only
  Markdown/XLSX/PPTX in `output-workspace` with matching embedded proof permissions
  can be downloaded. No directory listing, arbitrary path, symlink, or generation
  button. Artifact creation is a separate explicit Python agent capability.
- Questions/results/download bytes live in Streamlit session memory only. Reruns
  and downloads do not issue another model call or governed query.

## Meaning of read-only

No UI path writes source files, canonical/configuration tables, or artifact files.
The governed query service still appends its mandatory query-audit record. Thus
literal "zero writes to any store" is not asserted: it would contradict tickets
03/05 auditing. Streamlit's own runtime/cache and dependency metadata are also not
business stores. Tests scan the UI call/import surface and exercise actual UI
submission/downloads against real Postgres, comparing all business tables and
source/output file hashes; only `query_audit` may change.
