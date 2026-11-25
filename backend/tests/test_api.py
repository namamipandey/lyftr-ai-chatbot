import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.database import Store
from app.llm_service import Gateway, AllProvidersUnavailable


class FakeGateway:
    def __init__(self):
        self.cache = {}

    def answer(self, messages, header=None):
        key = tuple((m['role'], m['content']) for m in messages)
        if key in self.cache:
            return self.cache[key], dict(resolution_source='LLM_CACHE', model='test-model', latency_ms=1, input_tokens=12, output_tokens=3, key_id=None, fallback_attempts=0)
        if header and '*=429' in header:
            raise AllProvidersUnavailable()
        key_id = 'key_2' if header and 'key_1=' in header else 'key_1'
        reply = 'Example answer'
        self.cache[key] = reply
        return reply, dict(resolution_source='LIVE_INFERENCE', model='test-model', latency_ms=100, input_tokens=12, output_tokens=3, key_id=key_id, fallback_attempts=int(key_id == 'key_2'))


@pytest.fixture
def client(tmp_path):
    settings = Settings(('one','two'), 'test-model', f'sqlite:///{tmp_path}/test.db', ('http://localhost:3000',), True)
    app = create_app(settings, Store(settings.database_url), FakeGateway())
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get('/health').json() == {'status':'ok','keys_configured':2,'cache_enabled':True}


def test_chat_and_history(client):
    r = client.post('/chat', json={'session_id':'s1','message':'hello'})
    assert r.status_code == 200
    assert r.json()['metadata']['resolution_source'] == 'LIVE_INFERENCE'
    r2 = client.get('/sessions/s1/messages')
    assert [m['role'] for m in r2.json()['messages']] == ['user','assistant']
    assert r2.json()['messages'][1]['metadata']['input_tokens'] == 12


def test_cross_session_cache(client):
    client.post('/chat', json={'session_id':'s1','message':'hello'})
    r = client.post('/chat', json={'session_id':'s2','message':'hello'})
    assert r.json()['metadata']['resolution_source'] == 'LLM_CACHE'
    assert r.json()['metadata']['key_id'] is None


def test_failover_and_failure_no_history(client):
    r = client.post('/chat', headers={'X-Simulate-Failure':'key_1=429'}, json={'session_id':'s1','message':'fresh'})
    assert r.json()['metadata']['key_id'] == 'key_2'
    r = client.post('/chat', headers={'X-Simulate-Failure':'*=429'}, json={'session_id':'s2','message':'uncached'})
    assert r.status_code == 503
    assert r.json() == {'detail':'all providers unavailable'}
    assert client.get('/sessions/s2/messages').status_code == 404


@pytest.mark.parametrize('body', [{}, {'session_id':'s','message':' '}, {'session_id':'s','message':'x'*4001}, {'session_id':'x'*129,'message':'hi'}])
def test_validation(client, body):
    assert client.post('/chat', json=body).status_code == 422


def test_missing_session(client):
    assert client.get('/sessions/missing/messages').json() == {'detail':'session not found'}


def test_cache_identity(tmp_path):
    s = Settings(('a','b'),'test-model','sqlite:///tmp/a.db',(),True)
    gateway = Gateway(s)
    a = [{'role':'user','content':'hi'}]
    b = [{'role':'user','content':'bye'}]
    assert gateway.cache_key(a) != gateway.cache_key(b)
