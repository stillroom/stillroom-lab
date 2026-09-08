"""Streamlit acceptance: rendered proof, actual query, no persistent UI writes."""
import ast
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from openai import OpenAI
import pytest
from streamlit.testing.v1 import AppTest

from services.artifacts import OUTPUT, generate
from services.query import QueryRequest, QueryService
from services.store import Store
from test_agent import queries, transport, REQUEST  # noqa: F401 -- shared fixtures

ROOT = Path(__file__).resolve().parents[1]


def files_digest() -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in [ROOT / 'sources/generated', OUTPUT]
            for p in root.rglob('*') if p.is_file()}


def test_ui_default_fails_closed_without_db_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('STILLROOM_PROVIDER', raising=False)
    at = AppTest.from_file(str(ROOT / 'ui/app.py')).run()
    assert not at.exception
    at.text_area(key='question').set_value('Overdue invoices')
    at.button(key='ask').click().run()
    assert not at.exception
    assert 'Inference disabled' in at.error[0].value


def test_ui_renders_every_manifest_field_and_only_query_audit_changes(
    queries: QueryService, store: Store, monkeypatch: pytest.MonkeyPatch,
    transport: tuple[OpenAI, list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    from agent.provider import Provider

    client, _, requests = transport
    monkeypatch.setattr('agent.provider.provider_from_env', lambda: Provider(client, 'test-model'))
    monkeypatch.setenv('STILLROOM_SCHEMA', store.schema)
    monkeypatch.setenv('STILLROOM_ROLE', 'owner')
    monkeypatch.setenv('STILLROOM_CLIENT_ID', 'CLIENT-1')
    # Operator-generated artifact exists BEFORE the read-only UI starts.
    result = queries.execute(QueryRequest.model_validate(REQUEST))
    artifact = generate(result, OUTPUT / f'{result.query_id}.xlsx')
    try:
        before_files = files_digest()
        with store.transaction() as db:
            names = [row['tablename'] for row in db.execute(
                'SELECT tablename FROM pg_tables WHERE schemaname=%s', (store.schema,)).fetchall()]
            from psycopg import sql
            before = {name: db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(name))).fetchall()
                      for name in names}
        at = AppTest.from_file(str(ROOT / 'ui/app.py'), default_timeout=15).run()
        assert not at.exception
        at.text_area(key='question').set_value('Which overdue invoices have unresolved tickets?')
        at.date_input(key='as_of').set_value(date(2026, 9, 1))
        at.button(key='ask').click().run()
        assert not at.exception and not at.error
        answer = at.session_state['answer']
        assert json.loads(at.json[0].value) == answer.manifest.model_dump(mode='json')
        assert at.expander[0].label == 'Proof manifest — all fields'
        assert '700.00' in at.code[0].value and 'T001' in at.code[0].value
        at.text_input(key='artifact_name').set_value(artifact.name)
        at.button(key='load_artifact').click().run()
        assert not at.exception and not at.error
        assert len(at.get('download_button')) == 1
        assert len(requests) == 1  # reruns/downloads never repeat inference or queries
        assert files_digest() == before_files
        with store.transaction() as db:
            after = {name: db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(name))).fetchall()
                     for name in names}
        assert {k: v for k, v in before.items() if k != 'query_audit'} == {
            k: v for k, v in after.items() if k != 'query_audit'}
        assert len(after['query_audit']) == len(before['query_audit']) + 1
        assert all(a['retrieval_started'] for a in after['query_audit'])
    finally:
        artifact.unlink()


def test_ui_write_surface_is_explicitly_allowlisted() -> None:
    # Positive call allowlist: a new call or import requires review, not just a
    # blacklist that misses aliases. Transitive seams are exercised above.
    allowed_imports = {'datetime', 'os', 'streamlit', 'psycopg', 'agent.provider',
                       'agent.runner', 'services.query', 'services.downloads'}
    allowed_calls = {'main', 'date', 'os.getenv', 'PermissionContext', 'QueryService',
        'provider_from_env', 'Agent', 'agent.answer', 'provider.client.close', 'read_artifact',
        'answer.manifest.model_dump', 'st.set_page_config', 'st.title', 'st.caption',
        'st.text_area', 'st.date_input', 'st.checkbox', 'st.button', 'st.error', 'st.code',
        'st.expander', 'st.json', 'st.text_input', 'st.download_button',
        'st.session_state.get', 'st.session_state.pop', 'str'}
    def dotted(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return dotted(node.value) + '.' + node.attr
        return '<dynamic>'
    for path in (ROOT / 'ui').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(n.name in allowed_imports for n in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed_imports
            elif isinstance(node, ast.Call):
                assert dotted(node.func) in allowed_calls, (path.name, ast.unparse(node))
                assert not any(k.arg == 'artifact_formats' for k in node.keywords)
