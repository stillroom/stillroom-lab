# 05 — Agent + read-only UI

Status: open
Blocked by: 03 (can parallel with 04)
Executor: Astra

## Goal

One agent with typed tools and a Streamlit read-only front end with a proof drawer.
The agent proposes; the governed layer disposes.

## Work

1. Agent: single agent, typed tools only (allowlisted query calls, artifact
   generation calls). No free-form SQL tool. Tool schemas mirror the governed API.
2. Provider abstraction: one OpenAI-compatible client; provider selection via
   environment variable (OpenAI API / Ollama Cloud at 127.0.0.1:11434/v1). Cloud
   inference is explicit opt-in — the default config must be the local/no-op provider
   with a clear error, not a silent cloud call (test-verified).
3. Agent responses carry the proof manifest from the governed layer, unmodified.
4. Email corpus is treated as untrusted data: a test feeds the injected-instruction
   email and asserts the agent neither executes nor repeats the instruction as an
   action.
5. Streamlit UI: question input, answer pane, proof drawer (manifest visualisation:
   sources, snapshot, versions, query, conflicts), artifact download from
   output-workspace only. Read-only: no UI path mutates any store (test-verified by
   scanning the UI code's write surface).
6. Front end choice is deferrable (D6) — Streamlit now; the data layer is the same if
   Dash replaces it later.

## Acceptance criteria

- Agent answers case #1 end-to-end via typed tools only; manifest intact in UI.
- Injected-instruction email produces no tool call beyond the governed query path
  (test-verified).
- Default (no provider env) fails closed with a clear error — no silent cloud call.
- Proof drawer shows every manifest field for a sample answer.
- UI performs zero writes (verified by test + audit trail inspection).

## Non-goals

- No eve/Vercel deployment (untested; optional later). No multi-agent. No memory
  features. No auth system beyond the permission context.