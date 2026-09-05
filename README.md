# Stillroom Lab v0 — ticket 01

`spec.md` is the source of truth. This increment contains only the local Postgres
sandbox, repository scaffold, and deterministic fictional source fixtures.

## Prerequisites

- Linux with Docker Engine and Docker Compose (`--wait` support), accessible to your user.
- Python 3.11, `uv`, and GNU Make. No application service or cloud credentials needed.
- Local TCP port 55432 available. The Compose project name `stillroom-lab` is reserved
  for this disposable lab; do not reuse it for real data.

## Rebuild from a clean checkout

```sh
make seed
```

This installs locked Python dependencies in `.venv` and replaces only
`sources/generated/`. Python package caches and temporary files stay inside the
checkout. Faker uses the fixed seed 20260906 and the `en_AU` locale; dates and IDs
are fixed, money is serialized as decimal strings. `uv.lock` pins dependencies.
No Postgres connection is needed to seed the five file-based sources:

- `sources/generated/crm.sqlite` — customers and opportunities
- `sources/generated/invoices.csv` and `payments.csv`
- `sources/generated/support.json`
- `sources/generated/emails/*.txt`
- `sources/generated/policies/*.md` — mock Obsidian vault, frontmatter + wiki-links

See `sources/MESSINESS.md` for every deliberate trap and source record pointer.
Generated data is ignored by Git and rebuilt rather than manually maintained.
Do not run seed and fixture tests concurrently: they rebuild the same sandbox.

## Postgres scratch environment

```sh
docker compose up -d
docker compose exec -T postgres pg_isready -U lab -d lab
docker compose down -v
```

Only Postgres 15 runs. Host endpoint: `127.0.0.1:55432`; database/user `lab`,
password `lab-scratch-only` (public mock credential, never reuse for real data).
No extensions, ontology tables, service containers, or ingestion are installed.
The stock `postgres:15` tag tracks PostgreSQL 15 maintenance releases; source
fixture determinism does not depend on the Postgres image.

`stillroom-lab_pgdata` is a dedicated 256 MiB RAM-backed scratch volume. Data may
be lost on container stop or host reboot, not just `down -v`. Docker maintains its
own image/container/volume metadata in the daemon's storage; application source
and tooling files live in this checkout. Do not use this environment for durable
or private data. `down -v` affects this Compose project only, not Honcho.

## Verification

```sh
make typecheck
uv run --frozen pytest tests/test_seed.py
uv run --frozen pytest tests/test_policies.py
uv run --frozen pytest tests/test_messiness.py
uv run --frozen pytest tests/test_environment.py
# Final gate:
make test
```

The Docker test starts real Postgres, checks runtime loopback binding, writes a
probe table, destroys the volume, starts again and verifies the table is gone.
It stops and removes the scratch volume in cleanup. **The full suite resets this
lab database** and requires Docker; it does not silently skip unavailable Docker.
Seed tests compare all generated file bytes over consecutive runs and verify old
files are removed. Policy tests parse YAML and resolve wiki-links; fixture tests
read actual SQLite/CSV/JSON/text records and check documented traps.

These tests do not implement the ticket-06 benchmark. Later-ticket behavior
(permission enforcement, ingestion, metrics, proof manifests) is intentionally absent.
