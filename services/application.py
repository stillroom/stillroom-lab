"""Public ingestion and operator approval seam, separate from future queries."""
from pathlib import Path
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from services.records import CanonicalRecord, canonical_value
from services.sources import read_family, FIXTURE_OBSERVED_AT

from services.mapping import MappingContract, validate_mapping
from services.ontology import load_ontology
from services.store import Store

ROOT = Path(__file__).resolve().parents[1]


class UnapprovedMapping(ValueError):
    pass


class Application:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.ontology = load_ontology(ROOT / "ontology/v0.1.0.yaml")
        store.register_ontology(self.ontology)

    def register_mapping(self, mapping: MappingContract) -> None:
        self.store.register_mapping(validate_mapping(mapping.model_dump(), self.ontology))

    def approve_mapping(self, family: str, version: str, *, actor: str) -> None:
        self.store.approve_mapping(family, version, actor)

    def resolve_candidate(self, candidate_id: UUID, *, decision: str, actor: str) -> None:
        self.store.resolve_candidate(candidate_id, decision, actor)

    def ingest(self, family: str, version: str) -> int:
        mapping = self.store.mapping(family, version)
        if mapping.state != "approved":
            raise UnapprovedMapping("Mapping requires explicit operator approval")
        contract = validate_mapping(mapping.contract.model_dump(), self.ontology)
        rows = read_family(contract.family)
        retrieved_at = datetime.now(timezone.utc)
        count = 0
        with self.store.transaction() as db:
            for record_mapping in contract.records:
                matched = [row for row in rows if row.dataset == record_mapping.dataset]
                if not matched:
                    raise ValueError("Required source dataset is empty")
                for row in matched:
                    fields = self.ontology.entities[record_mapping.entity].fields
                    data = {target: canonical_value(row.values.get(source), fields[target])
                            for target, source in record_mapping.fields.items()}
                    raw_id = row.values.get(record_mapping.source_id)
                    if not isinstance(raw_id, str) or not raw_id.strip():
                        raise ValueError("Missing stable source ID")
                    observation_field = record_mapping.observation_field
                    observed_at = (date.fromisoformat(str(row.values[observation_field]))
                                   if observation_field else FIXTURE_OBSERVED_AT)
                    canonical_id = data["id"]
                    if not isinstance(canonical_id, str):
                        raise ValueError("Canonical ID must be a string")
                    snapshot_id = uuid4()
                    record = CanonicalRecord(
                        record_id=uuid4(), entity=record_mapping.entity,
                        canonical_id=canonical_id, data=data, family=contract.family,
                        source_id=f"{contract.family}:{row.dataset}:{raw_id}",
                        source_locator=row.locator, retrieved_at=retrieved_at,
                        snapshot_id=snapshot_id, mapping_version=contract.version,
                        ontology_version=contract.ontology_version,
                    )
                    db.execute("""INSERT INTO snapshots
                        (snapshot_id,family,source_locator,observed_at,observation_basis,
                         retrieved_at,content_digest,mapping_version,ontology_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (snapshot_id, contract.family, row.locator, observed_at,
                         f"source:{observation_field}" if observation_field else "ticket01-fixed-observation",
                         retrieved_at, row.content_digest, contract.version, contract.ontology_version))
                    db.execute("""INSERT INTO canonical_records
                        (record_id,entity,canonical_id,data,family,source_id,source_locator,
                         retrieved_at,snapshot_id,mapping_version,ontology_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (record.record_id, record.entity, record.canonical_id, Jsonb(data),
                         record.family, record.source_id, record.source_locator, retrieved_at,
                         snapshot_id, contract.version, contract.ontology_version))
                    count += 1
            # Identity remains source-based. Compare names only to propose review;
            # preserve both client partitions and pin evidence to the observed rows.
            pairs = db.execute("""SELECT DISTINCT ON (a.source_id,b.source_id)
                a.source_id AS left_id,b.source_id AS right_id,
                a.record_id AS left_record,b.record_id AS right_record
                FROM canonical_records a JOIN canonical_records b
                  ON lower(trim(a.data->>'name'))=lower(trim(b.data->>'name'))
                 AND a.source_id < b.source_id
                WHERE a.entity='Customer' AND b.entity='Customer'
                ORDER BY a.source_id,b.source_id,a.retrieved_at,b.retrieved_at""").fetchall()
            for pair in pairs:
                db.execute("""INSERT INTO resolution_candidates
                    (candidate_id,left_source_id,right_source_id,left_record_id,right_record_id,reason)
                    VALUES (%s,%s,%s,%s,%s,'duplicate-name; identity unresolved')
                    ON CONFLICT (left_source_id,right_source_id) DO NOTHING""",
                    (uuid4(), pair["left_id"], pair["right_id"], pair["left_record"], pair["right_record"]))
        return count
