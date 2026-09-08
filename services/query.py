"""Typed, deterministic governed-query boundary."""
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Literal
from decimal import Decimal

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import Field, ValidationError
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pathlib import Path
from typing import Any
import yaml

from services.ontology import StrictModel, load_ontology
from services.query_storage import READ_DSN, QueryAuditWriter
from services.proof import ProofManifest, SourceEvidence


class PermissionContext(StrictModel):
    role: str
    client_id: str


class QueryRequest(StrictModel):
    approved_query: str
    permission: PermissionContext
    as_of: date
    period_start: date | None = None


OutcomeCode = Literal['query_not_allowlisted', 'invalid_parameters', 'invalid_request',
                     'permission_denied', 'incomplete_evidence', 'query_failed']


class QueryReason(StrictModel):
    code: OutcomeCode
    message: str


Money = Annotated[Decimal, Field(strict=True, allow_inf_nan=False)]


class MetricRow(StrictModel):
    customer_id: str
    client_id: str
    observed_amount: Money
    amount: Money | None = None


class QueryResult(StrictModel):
    query_id: UUID
    snapshot_id: UUID
    reason: QueryReason
    rows: list[MetricRow]
    manifest: ProofManifest


class QueryService:
    def __init__(self, schema: str) -> None:
        self.schema = schema
        self.audit = QueryAuditWriter(schema)
        directory = Path(__file__).resolve().parents[1] / 'ontology'
        ontology = load_ontology(directory / 'v0.1.0.yaml')
        catalog = yaml.safe_load((directory / 'queries.v0.1.0.yaml').read_text())
        if catalog['ontology_version'] != ontology.version or catalog['version'] != ontology.version:
            raise ValueError('Query catalog must match the pinned ontology')
        relationships = {r.name for r in ontology.relationships}
        for name, definition in catalog['queries'].items():
            if name not in ontology.metrics or not set(definition['joins']) <= relationships:
                raise ValueError('Approved query references unknown ontology meaning')
        self.version = ontology.version
        self.approved: dict[str, dict[str, Any]] = {
            f'{self.version}/{name}': definition for name, definition in catalog['queries'].items()}

    def result(self, request: QueryRequest | None, rows: list[MetricRow],
               sources: list[SourceEvidence], reason: QueryReason, conflicts: list[str],
               mapping_versions: list[str], *,
               permission: PermissionContext | None = None) -> QueryResult:
        snapshot_id = uuid4()
        reference = request.approved_query if request and request.approved_query in self.approved else None
        permission = request.permission if request else permission
        manifest = ProofManifest(
            source_ids=sorted({s.source_id for s in sources}), retrieved_at=datetime.now(timezone.utc),
            snapshot_id=snapshot_id, ontology_version=self.version,
            mapping_versions=mapping_versions,
            approved_query=reference,
            metric_definition_ref=(f'ontology/{self.version}.yaml#metrics.{reference.split("/")[1]}'
                                   if reference else None),
            permission_context=permission.model_dump() if permission else None,
            unresolved_conflicts=sorted(set(conflicts) | {c for s in sources for c in s.conflicts}),
            sources=sources, caveats=[reason.message] + [
                f'{s.source_id}: no payment record found through {request.as_of if request else "unknown"}. '
                'Completeness check: not_established; not proof of nonpayment.'
                for s in sources if s.payment_absence],
            completeness_check='not_established', as_of=request.as_of if request else None,
            period_start=request.period_start if request else None)
        return QueryResult(query_id=uuid4(), snapshot_id=snapshot_id, rows=rows,
                           reason=reason, manifest=manifest)

    def reject_invalid(self, body: object, *, input_tokens: int = 0,
                       output_tokens: int = 0) -> QueryResult:
        """Audit malformed HTTP input without opening a retrieval connection."""
        fields = body if isinstance(body, dict) else {}
        reference = fields.get('approved_query')
        permission = fields.get('permission')
        reason = QueryReason(code='invalid_request', message='Request must match the governed query schema.')
        try:
            valid_permission = PermissionContext.model_validate(permission)
        except ValidationError:
            valid_permission = None
        result = self.result(None, [], [], reason, [], [], permission=valid_permission)
        self.audit.append({
            'query_id': result.query_id, 'snapshot_id': result.snapshot_id,
            'approved_query': reference if isinstance(reference, str) else '<invalid>',
            'permission': permission if isinstance(permission, dict) else {},
            'outcome': result.reason.code, 'retrieval_started': False, 'row_count': 0,
            'snapshots': [], 'ontology_version': self.version, 'mapping_versions': [],
            'as_of': None, 'period_start': None,
            'input_tokens': input_tokens, 'output_tokens': output_tokens,
        })
        return result

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(READ_DSN, row_factory=dict_row) as db:
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            db.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(self.schema)))
            yield db

    def execute(self, request: QueryRequest, *, input_tokens: int = 0,
                output_tokens: int = 0) -> QueryResult:
        rows: list[MetricRow] = []
        snapshots: list[dict[str, Any]] = []
        sources: list[SourceEvidence] = []
        conflicts: list[str] = []
        retrieval_started = False
        reason = QueryReason(code='query_not_allowlisted', message='Use a versioned approved-query reference.')
        if request.approved_query in self.approved:
            grants = {'owner': {'CLIENT-1', 'CLIENT-2', 'CLIENT-3'},
                      'analyst': {'CLIENT-1', 'CLIENT-2'}}
            reason = QueryReason(code='permission_denied', message='Role is not granted this client.')
            granted = request.permission.client_id in grants.get(request.permission.role, set())
            invalid_period = request.period_start is not None and (
                request.period_start > request.as_of or request.approved_query != f'{self.version}/cash_received')
            if granted and invalid_period:
                reason = QueryReason(code='invalid_parameters',
                    message='period_start is only valid for cash receipts and must not follow as_of.')
            if granted and not invalid_period:
                definition = self.approved[request.approved_query]
                retrieval_started = True
                try:
                    with self.connection() as db:
                        snapshots = db.execute("""SELECT s.snapshot_id::text, s.family,
                            s.mapping_version, s.ontology_version, s.content_digest,
                            s.observed_at::text, s.retrieved_at::text
                            FROM snapshots s JOIN mappings m ON m.family=s.family
                              AND m.version=s.mapping_version AND m.ontology_version=s.ontology_version
                            WHERE m.state='approved' AND s.ontology_version=%s
                            ORDER BY s.family,s.retrieved_at,s.snapshot_id""", (self.version,)).fetchall()
                        if 'unavailable' in definition:
                            reason = QueryReason(code='incomplete_evidence', message=definition['unavailable'])
                        else:
                            query = Path(__file__).with_name('query_scope.sql').read_text()
                            query += Path(__file__).with_name(definition['sql']).read_text()
                            values = db.execute(query, {
                                'snapshots': [s['snapshot_id'] for s in snapshots],
                                'client_id': request.permission.client_id, 'role': request.permission.role,
                                'as_of': request.as_of, 'period_start': request.period_start,
                            }).fetchall()
                            rows = [MetricRow.model_validate(value) for value in values]
                            proof_query = Path(__file__).with_name('query_scope.sql').read_text()
                            proof_query += Path(__file__).with_name('query_proof.sql').read_text()
                            evidence = db.execute(proof_query, {
                                'snapshots': [s['snapshot_id'] for s in snapshots],
                                'client_id': request.permission.client_id, 'role': request.permission.role,
                                'as_of': request.as_of, 'period_start': request.period_start,
                                'metric': request.approved_query.split('/')[1]}).fetchone()
                            if evidence is None:
                                raise ValueError('Proof query must return an evidence envelope')
                            sources = [SourceEvidence.model_validate(value) for value in evidence['sources']]
                            conflicts = evidence['conflicts']
                            reason = QueryReason(code='incomplete_evidence', message=definition['caveat'])
                except (psycopg.Error, ValidationError):
                    rows = []
                    sources = []
                    conflicts = []
                    reason = QueryReason(code='query_failed', message='Retrieval failed; no result is available.')
        mapping_versions = sorted({f"{s['family']}:{s['mapping_version']}" for s in snapshots})
        result = self.result(request, rows, sources, reason, conflicts, mapping_versions)
        self.audit.append({
            'query_id': result.query_id, 'snapshot_id': result.snapshot_id,
            'approved_query': request.approved_query, 'permission': request.permission.model_dump(),
            'outcome': reason.code, 'retrieval_started': retrieval_started, 'row_count': len(rows),
            'snapshots': snapshots, 'ontology_version': self.version,
            'mapping_versions': mapping_versions,
            'as_of': request.as_of, 'period_start': request.period_start,
            'input_tokens': input_tokens, 'output_tokens': output_tokens,
        })
        return result
