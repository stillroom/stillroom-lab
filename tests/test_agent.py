"""Ticket 05: provider opt-in and typed execution boundaries."""
from pathlib import Path

import pytest

import json
from datetime import date
from collections.abc import Iterator
from typing import Any

import httpx2
from openai import OpenAI

from services.query import PermissionContext, QueryRequest, QueryService
from services.query_storage import provision_queries
from services.store import Store
from test_ingestion import FAMILIES, approved_app

ROOT = Path(__file__).resolve().parents[1]
REQUEST = {'approved_query': 'v0.1.0/overdue_balances',
           'permission': {'role': 'owner', 'client_id': 'CLIENT-1'},
           'as_of': '2026-09-01', 'period_start': None}


@pytest.fixture
def queries(store: Store) -> QueryService:
    app = approved_app(store)
    for family in FAMILIES:
        app.ingest(family, 'v0.1.0')
    provision_queries(store)
    return QueryService(store.schema)


@pytest.fixture
def transport() -> Iterator[tuple[OpenAI, list[dict[str, Any]], list[dict[str, Any]]]]:
    calls = [{'id': 'call-query', 'type': 'function', 'function': {
        'name': 'governed_query', 'arguments': json.dumps(REQUEST)}}]
    requests: list[dict[str, Any]] = []
    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json={
            'id': 'test-completion', 'object': 'chat.completion', 'created': 0,
            'model': 'test-model', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'content': 'Untrusted model prose is not an answer.',
                            'tool_calls': calls}}],
            'usage': {'prompt_tokens': 41, 'completion_tokens': 12, 'total_tokens': 53}})
    with OpenAI(api_key='test-only', base_url='http://test.invalid/v1', max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(respond))) as client:
        yield client, calls, requests


def test_case_one_typed_query_preserves_proof_and_audits_usage(
    queries: QueryService, store: Store,
    transport: tuple[OpenAI, list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    from agent.provider import Provider
    from agent.runner import Agent

    client, _, requests = transport
    answer = Agent(queries, Provider(client, 'test-model')).answer(
        'Which overdue invoices have unresolved tickets?',
        PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1))
    assert len(requests) == 1
    system_prompt = requests[0]['messages'][0]['content']
    assert 'authoritative caller context, not an example' in system_prompt
    assert 'Do not ask the user to supply or change these values' in system_prompt
    assert [t['function']['name'] for t in requests[0]['tools']] == ['governed_query']
    schema = requests[0]['tools'][0]['function']['parameters']
    assert set(schema['properties']) == set(QueryRequest.model_fields)
    permission_schema = schema['properties']['permission']
    assert permission_schema.get('type') == 'object'
    assert permission_schema == PermissionContext.model_json_schema()
    assert '$defs' not in schema and '$ref' not in json.dumps(schema)
    assert schema['additionalProperties'] is False
    assert set(schema['properties']['approved_query']['enum']) == set(queries.approved)
    description = schema['properties']['approved_query']['description']
    assert 'v0.1.0/overdue_balances' in description
    assert 'unresolved-ticket evidence' in description
    assert 'customer-level' in description
    for definition in queries.approved.values():
        assert definition.get('caveat', definition.get('unavailable')) in description
    assert answer.manifest is answer.result.manifest
    expected = json.loads((ROOT / 'tests/query_expected.json').read_text())
    assert str(answer.result.rows[0].observed_amount) == expected['overdue_balances']['CLIENT-1']
    assert 'T001' in answer.text and '700.00' in answer.text
    assert 'Untrusted model prose' not in answer.text
    assert answer.artifacts == []
    with store.transaction() as db:
        audits = db.execute('SELECT * FROM query_audit').fetchall()
    assert len(audits) == 1
    assert audits[0]['input_tokens'] == 41 and audits[0]['output_tokens'] == 12
    assert audits[0]['permission'] == REQUEST['permission']


def test_explicit_artifact_tools_use_only_current_governed_result(
    queries: QueryService,
    transport: tuple[OpenAI, list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    from agent.provider import Provider
    from agent.runner import Agent
    from services.artifacts import OUTPUT
    from openpyxl import load_workbook

    client, calls, requests = transport
    for extension in ['md', 'xlsx']:
        calls.append({'id': f'call-{extension}', 'type': 'function', 'function': {
            'name': 'generate_artifact', 'arguments': json.dumps({'format': extension})}})
    answer = Agent(queries, Provider(client, 'test-model')).answer(
        'Overdue invoices and unresolved tickets, with spreadsheet and briefing.',
        PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1),
        artifact_formats=('md', 'xlsx'))
    assert [t['function']['name'] for t in requests[0]['tools']] == ['governed_query', 'generate_artifact']
    assert {p.suffix for p in answer.artifacts} == {'.md', '.xlsx'}
    assert all(p.parent == OUTPUT for p in answer.artifacts)
    for path in answer.artifacts:
        try:
            if path.suffix == '.md':
                payload = path.read_text().split('```json\n')[1].split('\n```')[0]
            else:
                book = load_workbook(path)
                payload = ''.join(str(row[0]) for row in book['Manifest'].values)
                assert book['Results']['C2'].value == '700.00'
                book.close()
            assert json.loads(payload) == answer.manifest.model_dump(mode='json')
        finally:
            path.unlink()


@pytest.mark.parametrize('attack', ['email', 'tool', 'sql', 'permission', 'permission_string',
                                  'permission_extra', 'date', 'extra', 'artifact', 'empty'])
def test_injected_email_and_hostile_proposals_have_no_extra_capabilities(
    queries: QueryService, store: Store,
    transport: tuple[OpenAI, list[dict[str, Any]], list[dict[str, Any]]], attack: str,
) -> None:
    from agent.provider import Provider
    from agent.runner import Agent, AgentError
    from services.artifacts import OUTPUT

    client, calls, requests = transport
    instruction = (ROOT / 'sources/generated/emails/E002.txt').read_text()
    before_files = sorted(p.name for p in OUTPUT.iterdir())
    with store.transaction() as db:
        before = db.execute('SELECT * FROM canonical_records ORDER BY record_id').fetchall()
    if attack == 'tool':
        calls[0]['function']['name'] = 'export_all_records'
    elif attack == 'artifact':
        calls.append({'id': 'evil', 'type': 'function', 'function': {
            'name': 'generate_artifact', 'arguments': '{"format":"xlsx"}'}})
    elif attack == 'empty':
        calls.clear()
    elif attack != 'email':
        request = json.loads(json.dumps(REQUEST))
        if attack == 'sql':
            request['approved_query'] = 'SELECT * FROM canonical_records'
        elif attack == 'permission':
            request['permission']['client_id'] = 'CLIENT-3'
        elif attack == 'permission_string':
            request['permission'] = json.dumps(request['permission'])
        elif attack == 'permission_extra':
            request['permission']['sql'] = 'SELECT * FROM canonical_records'
        elif attack == 'date':
            request['as_of'] = '2099-01-01'
        else:
            request['sql'] = 'DELETE FROM canonical_records'
        calls[0]['function']['arguments'] = json.dumps(request)
    agent = Agent(queries, Provider(client, 'test-model'))
    if attack == 'email':
        answer = agent.answer('Overdue invoices. Untrusted email follows:\n' + instruction,
            PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1))
        assert 'export all restricted' not in answer.text
        assert 'Ignore previous' not in answer.text
        assert answer.artifacts == []
    else:
        with pytest.raises(AgentError, match='Proposal rejected'):
            agent.answer(instruction, PermissionContext(role='owner', client_id='CLIENT-1'),
                         as_of=date(2026, 9, 1))
    assert len(requests) == 1  # No post-retrieval model turn, regardless of corpus content.
    if attack == 'empty':
        assert requests[0]['tool_choice'] == 'auto'  # Abstention must be possible on the wire.
    with store.transaction() as db:
        assert db.execute('SELECT * FROM canonical_records ORDER BY record_id').fetchall() == before
        audits = db.execute('SELECT * FROM query_audit').fetchall()
    assert len(audits) == 1
    assert audits[0]['retrieval_started'] is (attack == 'email')
    assert audits[0]['input_tokens'] == 41 and audits[0]['output_tokens'] == 12
    assert sorted(p.name for p in OUTPUT.iterdir()) == before_files


@pytest.mark.parametrize(('selected', 'url'), [
    ('openai', 'https://api.openai.com/v1/'),
    ('ollama-cloud', 'http://127.0.0.1:11434/v1/'),
])
def test_explicit_provider_has_fixed_endpoint_no_retries(
    monkeypatch: pytest.MonkeyPatch, selected: str, url: str,
) -> None:
    from agent.provider import provider_from_env

    monkeypatch.setenv('STILLROOM_PROVIDER', selected)
    monkeypatch.setenv('STILLROOM_MODEL', 'explicit-test-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://must-not-be-used.invalid/v1')
    provider = provider_from_env()  # constructing a real SDK client does not call it
    try:
        assert str(provider.client.base_url) == url
        assert provider.model == 'explicit-test-model'
        assert provider.client.max_retries == 0
        assert provider.client.timeout == 30.0
    finally:
        provider.client.close()


@pytest.mark.parametrize('selected', ['disabled', 'unknown', 'ollama-local'])
def test_disabled_unknown_or_unverified_local_provider_never_constructs_client(
    monkeypatch: pytest.MonkeyPatch, selected: str,
) -> None:
    from agent.provider import ProviderError, provider_from_env

    monkeypatch.setenv('STILLROOM_PROVIDER', selected)
    monkeypatch.setenv('STILLROOM_MODEL', 'cloud-model')
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail('Must fail before client construction')
    monkeypatch.setattr('agent.provider.OpenAI', forbidden)
    with pytest.raises(ProviderError):
        provider_from_env()


def test_openai_without_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.provider import ProviderError, provider_from_env

    monkeypatch.setenv('STILLROOM_PROVIDER', 'openai')
    monkeypatch.setenv('STILLROOM_MODEL', 'explicit-test-model')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ProviderError, match='OPENAI_API_KEY'):
        provider_from_env()


@pytest.mark.parametrize('failure', ['http', 'timeout', 'missing_usage', 'malformed'])
def test_provider_failure_never_executes_a_query(queries: QueryService, store: Store, failure: str) -> None:
    from agent.provider import Provider, ProviderError
    from agent.runner import Agent, AgentError

    seen: list[str] = []
    def respond(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.url.path)
        if failure == 'timeout':
            raise httpx2.ReadTimeout('test timeout', request=request)
        if failure == 'http':
            return httpx2.Response(503, json={'error': {'message': 'test unavailable'}})
        if failure == 'malformed':
            return httpx2.Response(200, json={'unexpected': 'not a completion'})
        return httpx2.Response(200, json={'id': 'test', 'object': 'chat.completion',
            'created': 0, 'model': 'test', 'choices': []})
    with OpenAI(api_key='test-only', base_url='http://test.invalid/v1', max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(respond))) as client:
        with pytest.raises((ProviderError, AgentError)):
            Agent(queries, Provider(client, 'test')).answer('Overdue invoices',
                PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1))
    assert seen == ['/v1/chat/completions']
    with store.transaction() as db:
        assert db.execute('SELECT * FROM query_audit').fetchall() == []


@pytest.mark.parametrize('field', ['prompt_tokens', 'completion_tokens'])
@pytest.mark.parametrize('tokens', [-1, 2147483648, 1.5, True, '1', 1.0])
def test_invalid_provider_usage_is_rejected_before_retrieval(
    queries: QueryService, monkeypatch: pytest.MonkeyPatch, field: str, tokens: int | float | str,
) -> None:
    from agent.provider import Provider
    from agent.runner import Agent, AgentError

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail('Invalid usage must be rejected before governed retrieval or audit')
    monkeypatch.setattr(queries, 'execute', forbidden)
    monkeypatch.setattr(queries, 'reject_invalid', forbidden)
    def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={'id': 'test', 'object': 'chat.completion',
            'created': 0, 'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'tool_calls': [{'id': 'test', 'type': 'function',
                    'function': {'name': 'governed_query', 'arguments': json.dumps(REQUEST)}}]}}],
            'usage': {'prompt_tokens': tokens if field == 'prompt_tokens' else 1,
                      'completion_tokens': tokens if field == 'completion_tokens' else 1,
                      'total_tokens': 2}})
    with OpenAI(api_key='test-only', base_url='http://test.invalid/v1', max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(respond))) as client:
        with pytest.raises(AgentError, match='token usage'):
            Agent(queries, Provider(client, 'test')).answer('Overdue invoices',
                PermissionContext(role='owner', client_id='CLIENT-1'), as_of=date(2026, 9, 1))


def test_default_provider_fails_before_client_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.provider import ProviderError, provider_from_env

    monkeypatch.delenv('STILLROOM_PROVIDER', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'irrelevant-test-key')
    monkeypatch.setenv('STILLROOM_MODEL', 'unused-cloud-model')
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail('Default provider must not construct a network client')
    monkeypatch.setattr('agent.provider.OpenAI', forbidden)
    with pytest.raises(ProviderError, match='disabled.*STILLROOM_PROVIDER'):
        provider_from_env()


@pytest.mark.parametrize('provider', ['openai', 'ollama-cloud', 'ollama-local'])
def test_provider_requires_explicit_model(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    from agent.provider import ProviderError, provider_from_env

    monkeypatch.setenv('STILLROOM_PROVIDER', provider)
    monkeypatch.delenv('STILLROOM_MODEL', raising=False)
    with pytest.raises(ProviderError, match='STILLROOM_MODEL'):
        provider_from_env()
