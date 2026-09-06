"""Separate operator provisioning and INSERT-only deterministic query auditing."""
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from services.store import Store

READ_DSN = 'host=127.0.0.1 port=55432 dbname=lab user=lab_query password=query-scratch-only connect_timeout=5'
AUDIT_DSN = 'host=127.0.0.1 port=55432 dbname=lab user=lab_query_audit password=audit-scratch-only connect_timeout=5'


def provision_queries(store: Store) -> None:
    """Operator startup only. QueryService never receives operator credentials."""
    with store.transaction() as db:
        db.execute(Path(__file__).with_name('query_schema.sql').read_text())
        for role in ('lab_query', 'lab_query_audit'):
            db.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
                sql.Identifier(store.schema), sql.Identifier(role)))
        db.execute('GRANT SELECT ON canonical_records, snapshots, mappings TO lab_query')
        db.execute('GRANT INSERT ON query_audit TO lab_query_audit')


class QueryAuditWriter:
    def __init__(self, schema: str) -> None:
        self.schema = schema

    def append(self, entry: dict[str, Any]) -> None:
        payload = {**entry}
        for name in ('permission', 'snapshots', 'mapping_versions'):
            payload[name] = Jsonb(payload[name])
        with psycopg.connect(AUDIT_DSN) as db:
            db.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(self.schema)))
            db.execute("""INSERT INTO query_audit
                (query_id,approved_query,permission,outcome,retrieval_started,row_count,
                 snapshot_id,snapshots,ontology_version,mapping_versions,as_of,period_start,input_tokens,output_tokens)
                VALUES (%(query_id)s,%(approved_query)s,%(permission)s,%(outcome)s,
                 %(retrieval_started)s,%(row_count)s,%(snapshot_id)s,%(snapshots)s,
                 %(ontology_version)s,%(mapping_versions)s,%(as_of)s,%(period_start)s,0,0)""", payload)
