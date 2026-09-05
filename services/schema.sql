-- Internal canonical sandbox only. No source connection uses these credentials.
CREATE TABLE IF NOT EXISTS ontology_versions (
    version text PRIMARY KEY CHECK (version = 'v0.1.0'),
    digest text NOT NULL, definition jsonb NOT NULL,
    registered_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS mappings (
    family text NOT NULL, version text NOT NULL,
    ontology_version text NOT NULL REFERENCES ontology_versions(version),
    digest text NOT NULL, contract jsonb NOT NULL,
    state text NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'approved', 'rejected')),
    approved_by text, approved_at timestamptz,
    PRIMARY KEY (family, version),
    CHECK ((state = 'approved' AND length(trim(approved_by)) > 0 AND approved_at IS NOT NULL)
        OR (state <> 'approved' AND approved_by IS NULL AND approved_at IS NULL))
);
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id uuid PRIMARY KEY,
    family text NOT NULL, source_locator text NOT NULL,
    observed_at date NOT NULL, observation_basis text NOT NULL,
    retrieved_at timestamptz NOT NULL, content_digest text NOT NULL,
    mapping_version text NOT NULL, ontology_version text NOT NULL REFERENCES ontology_versions(version),
    FOREIGN KEY (family, mapping_version) REFERENCES mappings(family, version),
    UNIQUE (snapshot_id, family, mapping_version, ontology_version, retrieved_at, source_locator)
);
CREATE TABLE IF NOT EXISTS canonical_records (
    record_id uuid PRIMARY KEY, entity text NOT NULL, canonical_id text NOT NULL,
    data jsonb NOT NULL, family text NOT NULL, source_id text NOT NULL,
    source_locator text NOT NULL, retrieved_at timestamptz NOT NULL,
    snapshot_id uuid NOT NULL, mapping_version text NOT NULL,
    ontology_version text NOT NULL,
    FOREIGN KEY (snapshot_id, family, mapping_version, ontology_version, retrieved_at, source_locator)
        REFERENCES snapshots(snapshot_id, family, mapping_version, ontology_version, retrieved_at, source_locator),
    UNIQUE (snapshot_id, entity, source_id)
);
CREATE TABLE IF NOT EXISTS resolution_candidates (
    candidate_id uuid PRIMARY KEY,
    left_source_id text NOT NULL, right_source_id text NOT NULL,
    left_record_id uuid NOT NULL REFERENCES canonical_records(record_id),
    right_record_id uuid NOT NULL REFERENCES canonical_records(record_id),
    reason text NOT NULL, state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','rejected')),
    reviewed_by text, reviewed_at timestamptz,
    UNIQUE (left_source_id,right_source_id), CHECK (left_source_id < right_source_id),
    CHECK ((state='pending' AND reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (state='rejected' AND reviewed_by IS NOT NULL AND length(trim(reviewed_by))>0 AND reviewed_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS resolution_decisions (
    decision_id bigserial PRIMARY KEY,
    candidate_id uuid NOT NULL REFERENCES resolution_candidates(candidate_id),
    decision text NOT NULL CHECK (decision IN ('merge-rejected','reject')),
    actor text NOT NULL CHECK (length(trim(actor))>0),
    decided_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Even direct SQL inserts cannot promote a proposed mapping into canonical data.
CREATE OR REPLACE FUNCTION require_approved_mapping() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM mappings WHERE family=NEW.family AND version=NEW.mapping_version
        AND ontology_version=NEW.ontology_version AND state='approved' FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Mapping requires explicit operator approval'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS snapshot_approval_gate ON snapshots;
CREATE TRIGGER snapshot_approval_gate BEFORE INSERT OR UPDATE ON snapshots
    FOR EACH ROW EXECUTE FUNCTION require_approved_mapping();
DROP TRIGGER IF EXISTS record_approval_gate ON canonical_records;
CREATE TRIGGER record_approval_gate BEFORE INSERT OR UPDATE ON canonical_records
    FOR EACH ROW EXECUTE FUNCTION require_approved_mapping();
