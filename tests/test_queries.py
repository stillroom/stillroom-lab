"""Governed API acceptance tests against the existing real Postgres fixture."""
from pathlib import Path
import json
import pytest
from datetime import date
from decimal import Decimal, FloatOperation, localcontext
import psycopg
from pydantic import ValidationError

from services.query import MetricRow, PermissionContext, QueryRequest, QueryService

from fastapi.testclient import TestClient

from services.api import create_app
from services.store import Store
from test_ingestion import FAMILIES, approved_app


def test_unapproved_query_is_rejected(store: Store) -> None:
    with TestClient(create_app(approved_app(store))) as client:
        response = client.post('/queries', json={
            'approved_query': 'SELECT * FROM canonical_records',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'},
            'as_of': '2026-09-01',
        })
    assert response.status_code == 422
    assert response.json()['reason']['code'] == 'query_not_allowlisted'
    assert response.json()['rows'] == []


def test_denial_and_rejection_are_audited_without_retrieval(store: Store) -> None:
    app = approved_app(store)
    with TestClient(create_app(app)) as client:
        for role, client_id in [('guest', 'CLIENT-1'), ('analyst', 'CLIENT-3'),
                                ('owner', "CLIENT-1' OR TRUE --")]:
            response = client.post('/queries', json={
                'approved_query': 'v0.1.0/cash_received',
                'permission': {'role': role, 'client_id': client_id}, 'as_of': '2026-09-01'})
            assert response.status_code == 403
            assert response.json()['rows'] == []
            with store.transaction() as db:
                audit = db.execute('SELECT * FROM query_audit WHERE query_id=%s',
                                   (response.json()['query_id'],)).fetchone()
            assert audit is not None
            assert audit['permission'] == {'role': role, 'client_id': client_id}
            assert audit['approved_query'] == 'v0.1.0/cash_received'
            assert audit['outcome'] == 'permission_denied'
            assert audit['retrieval_started'] is False
            assert audit['row_count'] == 0
            assert audit['snapshots'] == []
            assert audit['input_tokens'] == audit['output_tokens'] == 0
        response = client.post('/queries', json={
            'approved_query': 'v999/cash_received',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': '2026-09-01'})
        assert response.status_code == 422
    with store.transaction() as db:
        audits = db.execute('SELECT * FROM query_audit').fetchall()
    assert len(audits) == 4
    assert {a['outcome'] for a in audits} == {'permission_denied', 'query_not_allowlisted'}
    assert all(not a['retrieval_started'] and a['row_count'] == 0 for a in audits)


def test_cash_matches_independent_expecteds_including_zero_customers(store: Store) -> None:
    app = approved_app(store)
    expected = json.loads(Path(__file__).with_name('query_expected.json').read_text())
    # Construct before ingestion: a running API must see new committed snapshots.
    with TestClient(create_app(app)) as client:
        for family in FAMILIES:
            response = client.post('/ingestions', json={'family': family, 'mapping_version': 'v0.1.0'})
            assert response.status_code == 200
        for client_id, customer in [('CLIENT-1', 'C001'), ('CLIENT-2', 'C002'), ('CLIENT-3', 'C003')]:
            response = client.post('/queries', json={
                'approved_query': 'v0.1.0/cash_received',
                'permission': {'role': 'owner', 'client_id': client_id}, 'as_of': '2026-09-01'})
            assert response.status_code == 200, response.text
            assert response.json()['rows'] == [{'client_id': client_id, 'customer_id': customer,
                'observed_amount': expected['cash_received'][client_id], 'amount': None}]
            assert response.json()['reason']['code'] == 'incomplete_evidence'
            assert 'completeness' in response.json()['reason']['message']


def test_overdue_matches_independent_seed_expecteds(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    expected = json.loads(Path(__file__).with_name('query_expected.json').read_text())
    with TestClient(create_app(app)) as client:
        for client_id, customer in [('CLIENT-1', 'C001'), ('CLIENT-2', 'C002'), ('CLIENT-3', 'C003')]:
            response = client.post('/queries', json={
                'approved_query': 'v0.1.0/overdue_balances',
                'permission': {'role': 'owner', 'client_id': client_id}, 'as_of': '2026-09-01'})
            assert response.status_code == 200, response.text
            assert response.json()['rows'] == [{'client_id': client_id, 'customer_id': customer,
                'observed_amount': expected['overdue_balances'][client_id], 'amount': None}]
            assert response.json()['reason']['code'] == 'incomplete_evidence'
            assert 'authority' in response.json()['reason']['message']


@pytest.mark.parametrize(('metric', 'missing'), [('revenue', 'recognition'), ('pipeline', 'stage')])
def test_unprovable_metrics_abstain(store: Store, metric: str, missing: str) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    expected = json.loads(Path(__file__).with_name('query_expected.json').read_text())
    with TestClient(create_app(app)) as client:
        response = client.post('/queries', json={
            'approved_query': f'v0.1.0/{metric}',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': '2026-09-01'})
    assert response.status_code == 200
    assert response.json()['rows'] == expected[metric] == []
    assert response.json()['reason']['code'] == 'incomplete_evidence'
    assert missing in response.json()['reason']['message']
    with store.transaction() as db:
        audit = db.execute('SELECT * FROM query_audit').fetchone()
    assert audit is not None
    assert audit['outcome'] == 'incomplete_evidence'
    assert audit['row_count'] == 0


def test_money_has_no_float_path_in_service_or_http(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    with store.transaction() as db:
        db.execute("""UPDATE canonical_records SET data=jsonb_set(data,'{amount}',
            CASE canonical_id WHEN 'P001' THEN '"9007199254740993.01"'::jsonb
            ELSE '"-0.02"'::jsonb END) WHERE entity='Payment'""")
    request = QueryRequest(approved_query='v0.1.0/cash_received',
        permission=PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1))
    with TestClient(create_app(app)) as client:
        with localcontext() as context:
            context.traps[FloatOperation] = True
            result = QueryService(store.schema).execute(request)
            assert type(result.rows[0].observed_amount) is Decimal
            assert result.rows[0].observed_amount == Decimal('9007199254740992.99')
            assert not context.flags[FloatOperation]
        response = client.post('/queries', json=request.model_dump(mode='json'))
        assert response.status_code == 200
        assert response.json()['rows'][0]['observed_amount'] == '9007199254740992.99'
    with pytest.raises(ValidationError):
        MetricRow.model_validate({'customer_id': 'C001', 'client_id': 'CLIENT-1',
                                  'observed_amount': 0.1})


def test_query_credentials_cannot_write_at_db_layer(store: Store) -> None:
    create_app(approved_app(store))
    queries = QueryService(store.schema)
    with queries.connection() as db:
        assert db.execute('SELECT current_user AS role').fetchone() == {'role': 'lab_query'}
        assert db.execute('SHOW transaction_read_only').fetchone() == {'transaction_read_only': 'on'}
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        with queries.connection() as db:
            db.execute('DELETE FROM canonical_records')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with queries.connection() as db:
            db.execute('SET TRANSACTION READ WRITE')
            db.execute('DELETE FROM canonical_records')


def test_complete_audit_and_denial_without_select_privileges(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    snapshots = {str(s.snapshot_id) for s in store.snapshots()}
    request = {'approved_query': 'v0.1.0/cash_received',
               'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': '2026-09-01'}
    with TestClient(create_app(app)) as client:
        success = client.post('/queries', json=request)
        assert success.status_code == 200
        with store.transaction() as db:
            db.execute('REVOKE SELECT ON canonical_records, snapshots, mappings FROM lab_query')
        denial = client.post('/queries', json={**request,
            'permission': {'role': 'analyst', 'client_id': 'CLIENT-3'}})
        assert denial.status_code == 403
        rejection = client.post('/queries', json={**request, 'approved_query': 'v999/cash_received'})
        assert rejection.status_code == 422
        failure = client.post('/queries', json=request)
        assert failure.status_code == 503
        assert failure.json()['rows'] == []
    with store.transaction() as db:
        audits = db.execute('SELECT * FROM query_audit ORDER BY created_at').fetchall()
    assert len(audits) == 4
    for audit, response, outcome, started, count in zip(audits,
        [success, denial, rejection, failure],
        ['incomplete_evidence', 'permission_denied', 'query_not_allowlisted', 'query_failed'],
        [True, False, False, True], [1, 0, 0, 0], strict=True):
        assert str(audit['query_id']) == response.json()['query_id']
        assert str(audit['snapshot_id']) == response.json()['snapshot_id']
        assert audit['outcome'] == outcome
        assert audit['retrieval_started'] is started
        assert audit['row_count'] == count
        assert audit['ontology_version'] == 'v0.1.0'
        assert audit['as_of'] == date(2026, 9, 1)
        assert audit['input_tokens'] == audit['output_tokens'] == 0
        submitted = json.loads(response.request.content)
        assert audit['approved_query'] == submitted['approved_query']
        assert audit['permission'] == submitted['permission']
    assert {s['snapshot_id'] for s in audits[0]['snapshots']} == snapshots
    assert audits[0]['mapping_versions'] == [
        'billing:v0.1.0', 'crm:v0.1.0', 'email:v0.1.0', 'policy:v0.1.0', 'support:v0.1.0']
    assert all(a['snapshots'] == [] and a['mapping_versions'] == [] for a in audits[1:])
    print('AUDIT_EVIDENCE=' + json.dumps(audits, default=str, sort_keys=True))


def test_receipt_period_and_overdue_date_boundaries(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    with TestClient(create_app(app)) as client:
        for metric, as_of, start, expected in [
            ('cash_received', '2026-08-09', None, '0.00'),
            ('cash_received', '2026-08-10', None, '400.00'),
            ('cash_received', '2026-08-11', '2026-08-11', '-100.00'),
            ('overdue_balances', '2026-08-15', None, '0.00'),
            ('overdue_balances', '2026-08-16', None, '700.00')]:
            response = client.post('/queries', json={
                'approved_query': f'v0.1.0/{metric}',
                'permission': {'role': 'owner', 'client_id': 'CLIENT-1'},
                'as_of': as_of, 'period_start': start})
            assert response.status_code == 200, response.text
            assert response.json()['rows'][0]['observed_amount'] == expected
            with store.transaction() as db:
                audit = db.execute('SELECT period_start FROM query_audit WHERE query_id=%s',
                                   (response.json()['query_id'],)).fetchone()
            assert audit == {'period_start': date.fromisoformat(start) if start else None}


def test_nonfinite_canonical_money_fails_closed_and_is_audited(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    with store.transaction() as db:
        db.execute("""UPDATE canonical_records SET data=jsonb_set(data,'{amount}','"NaN"'::jsonb)
                      WHERE entity='Payment' AND canonical_id='P001'""")
    with TestClient(create_app(app)) as client:
        response = client.post('/queries', json={
            'approved_query': 'v0.1.0/cash_received',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': '2026-09-01'})
    assert response.status_code == 503
    assert response.json()['rows'] == []
    with store.transaction() as db:
        audit = db.execute('SELECT outcome,row_count,retrieval_started FROM query_audit').fetchone()
    assert audit == {'outcome': 'query_failed', 'row_count': 0, 'retrieval_started': True}


@pytest.mark.parametrize(('metric', 'start'), [
    ('cash_received', '2026-09-02'), ('overdue_balances', '2026-08-01')])
def test_invalid_period_is_rejected_and_audited_before_retrieval(
    store: Store, metric: str, start: str,
) -> None:
    with TestClient(create_app(approved_app(store))) as client:
        response = client.post('/queries', json={
            'approved_query': f'v0.1.0/{metric}',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'},
            'as_of': '2026-09-01', 'period_start': start})
    assert response.status_code == 422
    assert response.json()['reason']['code'] == 'invalid_parameters'
    assert response.json()['rows'] == []
    with store.transaction() as db:
        audit = db.execute('SELECT outcome,row_count,retrieval_started FROM query_audit').fetchone()
    assert audit == {'outcome': 'invalid_parameters', 'row_count': 0, 'retrieval_started': False}


@pytest.mark.parametrize('as_of', [None, 'not-a-date'])
def test_malformed_query_attempt_is_audited(store: Store, as_of: str | None) -> None:
    with TestClient(create_app(approved_app(store))) as client:
        response = client.post('/queries', json={
            'approved_query': 'v0.1.0/cash_received',
            'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': as_of})
    assert response.status_code == 422
    assert response.json()['reason']['code'] == 'invalid_request'
    assert response.json()['rows'] == []
    with store.transaction() as db:
        audit = db.execute('SELECT * FROM query_audit WHERE query_id=%s',
                           (response.json()['query_id'],)).fetchone()
    assert audit is not None
    assert audit['approved_query'] == 'v0.1.0/cash_received'
    assert audit['permission'] == {'role': 'owner', 'client_id': 'CLIENT-1'}
    assert audit['outcome'] == 'invalid_request'
    assert audit['retrieval_started'] is False
    assert audit['row_count'] == 0
    assert audit['as_of'] is None
    assert audit['snapshots'] == audit['mapping_versions'] == []
    assert audit['input_tokens'] == audit['output_tokens'] == 0
