-- Local operator provisioning; neither query role owns the canonical store.
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='lab_query') THEN
        CREATE ROLE lab_query LOGIN PASSWORD 'query-scratch-only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='lab_query_audit') THEN
        CREATE ROLE lab_query_audit LOGIN PASSWORD 'audit-scratch-only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END $$;
ALTER ROLE lab_query SET default_transaction_read_only=on;
CREATE TABLE IF NOT EXISTS query_audit (
    query_id uuid PRIMARY KEY,
    approved_query text NOT NULL,
    permission jsonb NOT NULL,
    outcome text NOT NULL,
    retrieval_started boolean NOT NULL,
    row_count integer NOT NULL CHECK (row_count >= 0),
    -- Identifies the per-call snapshot bundle below, not an invented source snapshot.
    snapshot_id uuid NOT NULL UNIQUE,
    snapshots jsonb NOT NULL,
    ontology_version text NOT NULL,
    mapping_versions jsonb NOT NULL,
    as_of date, -- NULL only when the request cannot be validated.
    period_start date,
    -- Zero for pure deterministic queries; a future model call logs real usage.
    input_tokens integer NOT NULL CHECK (input_tokens >= 0),
    output_tokens integer NOT NULL CHECK (output_tokens >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (retrieval_started OR row_count=0)
);
