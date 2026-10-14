"""Authenticated card API using real agents, SQLite copies and fake models."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import shutil
import sqlite3
from threading import Event
from uuid import uuid4

import pytest

from agent.context_budget import ContextPolicy
from agent.react_agent import ReactAgent
from service_desk.db import init_db
from service_desk.tools import execute_service_tool
from test_api import AUTH, service, session, error_code, entered
from test_core_flows import ScriptedModel, answer, call


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    return init_db(tmp_path_factory.mktemp('service-action-api') / 'seed.db')


@pytest.fixture
def db(template, tmp_path):
    path = tmp_path / 'service.db'
    shutil.copyfile(template, path)
    return path


@asynccontextmanager
async def action_service(monkeypatch, db, *, responses=(), toolset='service', factory_hook=None):
    monkeypatch.setenv('AGENT_TOOLSET', toolset)

    def factory(**kwargs):
        agent = ReactAgent(**kwargs, service_db_path=db, model=ScriptedModel(responses=list(responses)),
                           context_policy=ContextPolicy(window_tokens=32768, reserve_output_tokens=1024,
                                                        reasoning_enabled=False))
        if factory_hook:
            factory_hook(agent)
        return agent

    async with service(factory=factory) as pair:
        yield pair


async def ready_session(app, client, user='1002'):
    sid = await session(client, user_id=user)
    response = await client.get(f'/v1/sessions/{sid}/actions', headers=AUTH)
    assert response.status_code == 200 and response.json() == []
    return sid, app.state.manager.sessions[sid]


def propose(server):
    return json.loads(execute_service_tool('propose_order',
                      {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1}, server.service_state))


def status(db, action_id):
    with sqlite3.connect(db) as connection:
        return connection.execute('SELECT status FROM pending_actions WHERE action_id=?', (action_id,)).fetchone()[0]


@pytest.mark.parametrize('method,suffix', [('get', ''), ('post', '/fake/confirm'), ('post', '/fake/reject')])
def test_card_routes_require_bearer_before_any_work(monkeypatch, db, method, suffix):
    async def scenario():
        async with action_service(monkeypatch, db) as (app, client):
            sid = await session(client, user_id='1002')
            response = await getattr(client, method)(f'/v1/sessions/{sid}/actions{suffix}')
            error_code(response, 401, 'unauthorized')
            assert app.state.manager.sessions[sid].agent is None
            assert app.state.manager.jobs == set()
    asyncio.run(scenario())


@pytest.mark.parametrize('operation', ['confirm', 'reject'])
@pytest.mark.parametrize('other_user', ['1002', '1003'])
def test_foreign_action_and_missing_action_have_identical_404_body(monkeypatch, db, operation, other_user):
    async def scenario():
        async with action_service(monkeypatch, db) as (app, client):
            owner, server = await ready_session(app, client)
            pending = propose(server)
            other, requester = await ready_session(app, client, other_user)
            actual = await client.post(f"/v1/sessions/{other}/actions/{pending['action_id']}/{operation}", headers=AUTH)
            absent = await client.post(f'/v1/sessions/{other}/actions/{uuid4()}/{operation}', headers=AUTH)
            assert actual.status_code == absent.status_code == 404
            assert actual.content == absent.content
            assert actual.json()['error']['code'] == 'action_not_found'
            assert actual.headers['x-request-id'] and absent.headers['x-request-id']
            assert requester.agent.messages == server.agent.messages == []
            assert status(db, pending['action_id']) == 'pending'
            assert (await client.get(f'/v1/sessions/{other}/actions', headers=AUTH)).json() == []
            cards = (await client.get(f'/v1/sessions/{owner}/actions', headers=AUTH)).json()
            assert [card['action_id'] for card in cards] == [pending['action_id']]
    asyncio.run(scenario())


@pytest.mark.parametrize('terminal', ['executed', 'rejected', 'expired', 'superseded', 'failed'])
def test_card_terminal_results_are_200_and_recorded_once(monkeypatch, db, terminal):
    async def scenario():
        async with action_service(monkeypatch, db) as (app, client):
            sid, server = await ready_session(app, client)
            pending = propose(server)
            action_id = pending['action_id']
            if terminal == 'expired':
                with sqlite3.connect(db) as connection:
                    connection.execute('UPDATE pending_actions SET expires_at=? WHERE action_id=?',
                                       ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), action_id))
            if terminal == 'superseded':
                propose(server)
            if terminal == 'failed':
                with sqlite3.connect(db) as connection:
                    connection.execute("UPDATE consumables SET stock=0 WHERE sku='SKU-FILTER'")
            operation = 'reject' if terminal == 'rejected' else 'confirm'
            url = f'/v1/sessions/{sid}/actions/{action_id}/{operation}'
            first = await client.post(url, headers=AUTH, json={})
            assert first.status_code == 200 and first.json()['status'] == terminal
            assert first.json()['message']
            history = list(server.agent.messages)
            assert len(history) == 2 and history[0].name == 'action_event'
            assert history[1].content == first.json()['message']
            second = await client.post(url, headers=AUTH)
            assert second.status_code == 200 and second.json() == first.json()
            assert server.agent.messages == history
            assert server.agent.agent is not None
            assert server.agent.summary_model.seen == []
    asyncio.run(scenario())


@pytest.mark.parametrize('operation', ['confirm', 'reject'])
@pytest.mark.parametrize('field', ['session_id', 'user_id', 'service_db_path', 'db_path', 'args', 'action_id'])
def test_card_requests_reject_all_body_fields(monkeypatch, db, operation, field):
    async def scenario():
        async with action_service(monkeypatch, db) as (app, client):
            sid, server = await ready_session(app, client)
            pending = propose(server)
            response = await client.post(f"/v1/sessions/{sid}/actions/{pending['action_id']}/{operation}",
                                         headers=AUTH, json={field: 'forged'})
            error_code(response, 422, 'invalid_request')
            assert status(db, pending['action_id']) == 'pending' and server.agent.messages == []
    asyncio.run(scenario())


def test_messages_include_only_owned_pending_cards_and_api_session_binding(monkeypatch, db):
    async def scenario():
        responses = [call('propose_order', device_id='D-1002-01', sku='SKU-FILTER', qty=1),
                     answer('请使用卡片确认'), answer('处理完成')]
        async with action_service(monkeypatch, db, responses=responses) as (app, client):
            sid = await session(client, user_id='1002')
            response = await client.post(f'/v1/sessions/{sid}/messages', headers=AUTH, json={'query': '购买滤网'})
            assert response.status_code == 200
            cards = response.json()['actions']
            assert len(cards) == 1 and cards[0]['status'] == 'pending'
            server = app.state.manager.sessions[sid]
            assert server.agent.session_id == server.service_state['session_id'] == sid
            assert server.agent.service_state['user_id'] == server.user_id == '1002'
            with sqlite3.connect(db) as connection:
                assert connection.execute('SELECT session_id,user_id FROM pending_actions').fetchone() == (sid, '1002')
            assert (await client.get(f'/v1/sessions/{sid}/actions', headers=AUTH)).json() == cards
            result = await client.post(f"/v1/sessions/{sid}/actions/{cards[0]['action_id']}/confirm", headers=AUTH)
            assert result.status_code == 200 and result.json()['status'] == 'executed'
            second = await client.post(f'/v1/sessions/{sid}/messages', headers=AUTH, json={'query': '接下来呢'})
            assert second.status_code == 200 and second.json()['actions'] == []
            assert result.json()['message'] in [m.content for m in server.agent.summary_model.seen[-1]]
    asyncio.run(scenario())


def test_action_routes_use_server_identity_even_if_factory_initial_id_differs(monkeypatch, db):
    async def scenario():
        def mismatched(agent):
            agent.user_id = '1003'
            agent.session_id = 'wrong-session'
            agent.service_state.update(user_id='1003', session_id='wrong-session')

        async with action_service(monkeypatch, db, factory_hook=mismatched) as (app, client):
            sid, server = await ready_session(app, client)
            assert server.service_state['user_id'] == server.agent.user_id == '1002'
            assert server.service_state['session_id'] == server.agent.session_id == sid
            pending = propose(server)
            response = await client.post(f"/v1/sessions/{sid}/actions/{pending['action_id']}/confirm", headers=AUTH)
            assert response.status_code == 200 and response.json()['status'] == 'executed'
    asyncio.run(scenario())


def test_running_round_blocks_all_card_routes_and_preserves_pending(monkeypatch, db):
    async def scenario():
        started, release = Event(), Event()

        def block(agent):
            original = agent.execute_stream

            def execute(query, **kwargs):
                started.set()
                assert release.wait(5)
                yield from original(query, **kwargs)

            agent.execute_stream = execute

        async with action_service(monkeypatch, db, responses=[answer('完成')], factory_hook=block) as (app, client):
            sid, server = await ready_session(app, client)
            pending = propose(server)
            request = asyncio.create_task(client.post(f'/v1/sessions/{sid}/messages', headers=AUTH, json={'query': '问题'}))
            await entered(started)
            try:
                for method, suffix in [('get', ''), ('post', '/confirm'), ('post', '/reject')]:
                    path = f'/v1/sessions/{sid}/actions'
                    if suffix:
                        path += '/' + pending['action_id'] + suffix
                    error_code(await getattr(client, method)(path, headers=AUTH), 409, 'session_busy')
                assert server.agent.messages == [] and status(db, pending['action_id']) == 'pending'
            finally:
                release.set()
                assert (await request).status_code == 200
    asyncio.run(scenario())


@pytest.mark.parametrize('method,suffix', [('get', ''), ('post', '/fake/confirm'), ('post', '/fake/reject')])
def test_legacy_card_routes_disabled_and_message_shape_unchanged(monkeypatch, db, method, suffix):
    async def scenario():
        async with action_service(monkeypatch, db, toolset='legacy', responses=[answer('legacy 回答')]) as (app, client):
            sid = await session(client, user_id='1002')
            response = await getattr(client, method)(f'/v1/sessions/{sid}/actions{suffix}', headers=AUTH)
            error_code(response, 409, 'service_disabled')
            assert app.state.manager.sessions[sid].agent.messages == []
            reply = await client.post(f'/v1/sessions/{sid}/messages', headers=AUTH, json={'query': '你好'})
            assert reply.status_code == 200 and 'actions' not in reply.json()
    asyncio.run(scenario())


def test_messages_empty_pending_list_and_all_card_routes_in_openapi(monkeypatch, db):
    async def scenario():
        async with action_service(monkeypatch, db, responses=[answer('你好')]) as (_, client):
            sid = await session(client, user_id='1002')
            reply = await client.post(f'/v1/sessions/{sid}/messages', headers=AUTH, json={'query': '你好'})
            assert reply.status_code == 200 and reply.json()['actions'] == []
            schema = (await client.get('/openapi.json')).json()
            for suffix, method in [('', 'get'), ('/{action_id}/confirm', 'post'), ('/{action_id}/reject', 'post')]:
                operation = schema['paths']['/v1/sessions/{session_id}/actions' + suffix][method]
                assert operation['security'] == [{'APIKey': []}]
    asyncio.run(scenario())
