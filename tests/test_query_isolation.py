"""Client isolation at the governed API, using adversarial canonical observations."""
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest

from services.api import create_app
from services.store import Store
from test_ingestion import FAMILIES, approved_app, source_bytes


def add_observation(store: Store, entity: str, original_id: str, canonical_id: str,
                    source_id: str | None, changes: dict[str, str]) -> None:
    """Keep sources byte-identical; insert a provenance-valid scratch observation."""
    snapshot_id = uuid4()
    with store.transaction() as db:
        original = db.execute('''SELECT * FROM canonical_records WHERE entity=%s
            AND canonical_id=%s ORDER BY retrieved_at LIMIT 1''', (entity, original_id)).fetchone()
        assert original is not None
        db.execute('''INSERT INTO snapshots SELECT %s,family,source_locator,observed_at,
            observation_basis,clock_timestamp(),content_digest,mapping_version,ontology_version
            FROM snapshots WHERE snapshot_id=%s''', (snapshot_id, original['snapshot_id']))
        db.execute('''INSERT INTO canonical_records
            SELECT %s,%s,%s,%s,family,%s,source_locator,retrieved_at,snapshot_id,
                mapping_version,ontology_version FROM snapshots WHERE snapshot_id=%s''',
            (uuid4(), entity, canonical_id, Jsonb({**original['data'], **changes, 'id': canonical_id}),
             source_id or original['source_id'], snapshot_id))


@pytest.mark.parametrize('same_source_id', [False, True])
@pytest.mark.parametrize(('entity', 'original', 'changes'), [
    ('Customer', 'C001', {'account_id': 'CLIENT-2'}),
    ('Invoice', 'I001', {'customer_id': 'C002'}),
    ('Payment', 'P001', {'invoice_id': 'IB'}),
])
def test_shared_ids_abstain_in_both_client_directions(
    store: Store, same_source_id: bool, entity: str, original: str, changes: dict[str, str],
) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    add_observation(store, 'Invoice', 'I001', 'IB', 'billing:invoices:IB',
                    {'customer_id': 'C002', 'amount': '50.00'})
    add_observation(store, entity, original, original,
                    None if same_source_id else f'second-client:{original}', changes)
    with TestClient(create_app(app)) as client:
        for client_id in ('CLIENT-1', 'CLIENT-2'):
            for metric in ('cash_received', 'overdue_balances'):
                response = client.post('/queries', json={
                    'approved_query': f'v0.1.0/{metric}',
                    'permission': {'role': 'owner', 'client_id': client_id}, 'as_of': '2026-09-01'})
                assert response.status_code == 200
                assert response.json()['rows'] == []
                assert response.json()['reason']['code'] == 'incomplete_evidence'


def test_reused_source_id_with_different_canonical_id_abstains(store: Store) -> None:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    add_observation(store, 'Invoice', 'I001', 'IB', 'billing:invoices:IB',
                    {'customer_id': 'C002', 'amount': '50.00'})
    add_observation(store, 'Payment', 'P001', 'PX', None, {'invoice_id': 'IB'})
    with TestClient(create_app(app)) as client:
        for client_id in ('CLIENT-2', 'CLIENT-1'):
            for metric in ('cash_received', 'overdue_balances'):
                response = client.post('/queries', json={
                    'approved_query': f'v0.1.0/{metric}',
                    'permission': {'role': 'owner', 'client_id': client_id}, 'as_of': '2026-09-01'})
                assert response.status_code == 200
                assert response.json()['rows'] == []
                assert response.json()['reason']['code'] == 'incomplete_evidence'


def test_every_seed_trap_with_nonempty_client_controls(store: Store) -> None:
    before = source_bytes()
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    # Shared-name C002 and restricted C003 must each have their OWN money.
    for customer, invoice, payment, billed, paid in [
        ('C002', 'IB', 'PB', '50.00', '37.01'), ('C003', 'IC', 'PC', '100.00', '5.00')]:
        add_observation(store, 'Invoice', 'I001', invoice, f'billing:invoices:{invoice}',
                        {'customer_id': customer, 'amount': billed})
        add_observation(store, 'Payment', 'P001', payment, f'billing:payments:{payment}',
                        {'invoice_id': invoice, 'amount': paid})
    with TestClient(create_app(app)) as client:
        for role, client_id, customer, cash, overdue in [
            ('owner', 'CLIENT-1', 'C001', '300.00', '700.00'),
            ('analyst', 'CLIENT-2', 'C002', '37.01', '12.99'),
            ('owner', 'CLIENT-3', 'C003', '5.00', '95.00')]:
            for metric, expected in [('cash_received', cash), ('overdue_balances', overdue),
                                     ('revenue', None), ('pipeline', None)]:
                response = client.post('/queries', json={
                    'approved_query': f'v0.1.0/{metric}',
                    'permission': {'role': role, 'client_id': client_id}, 'as_of': '2026-09-01'})
                assert response.status_code == 200
                assert response.json()['rows'] == ([] if expected is None else [{
                    'client_id': client_id, 'customer_id': customer,
                    'observed_amount': expected, 'amount': None}])
    assert source_bytes() == before


def test_reingesting_unchanged_snapshots_does_not_double_money(store: Store) -> None:
    app = approved_app(store)
    with TestClient(create_app(app)) as client:
        for _ in range(2):
            for family in FAMILIES:
                app.ingest(family, 'v0.1.0')
            response = client.post('/queries', json={
                'approved_query': 'v0.1.0/cash_received',
                'permission': {'role': 'owner', 'client_id': 'CLIENT-1'}, 'as_of': '2026-09-01'})
            assert response.json()['rows'][0]['observed_amount'] == '300.00'
