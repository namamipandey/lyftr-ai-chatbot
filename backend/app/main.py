import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .database import Store
from .llm_service import AllProvidersUnavailable, Gateway
from .schemas import ChatRequest

logger = logging.getLogger(__name__)


def create_app(settings=None, store=None, gateway=None):
    settings = settings or get_settings()
    store = store or Store(settings.database_url)
    gateway = gateway or Gateway(settings)

    @asynccontextmanager
    async def lifespan(app):
        store.ping()
        if len(settings.keys) < 2:
            logger.warning('Fewer than two API keys configured; health will be unavailable')
        yield

    app = FastAPI(title='Lyftr AI Chat API', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['*'])

    @app.get('/health')
    def health():
        try:
            store.ping()
        except Exception:
            raise HTTPException(503, detail='database unavailable')
        if len(settings.keys) < 2:
            raise HTTPException(503, detail='key pool unavailable')
        return {'status': 'ok', 'keys_configured': len(settings.keys), 'cache_enabled': True}

    @app.post('/chat')
    async def chat(request: ChatRequest, x_simulate_failure: str | None = Header(default=None)):
        history = await run_in_threadpool(store.history, request.session_id)
        messages = [{'role': 'system', 'content': request.system_prompt if request.system_prompt is not None else 'You are a helpful assistant.'}]
        messages.extend({'role': item['role'], 'content': item['content']} for item in history)
        messages.append({'role': 'user', 'content': request.message})
        try:
            reply, metadata = await run_in_threadpool(gateway.answer, messages, x_simulate_failure)
        except AllProvidersUnavailable:
            raise HTTPException(503, detail='all providers unavailable')
        except Exception:
            logger.exception('Chat inference failed')
            raise HTTPException(503, detail='all providers unavailable')
        await run_in_threadpool(store.append_exchange, request.session_id, request.message, reply, metadata)
        return {'session_id': request.session_id, 'reply': reply, 'metadata': metadata}

    @app.get('/sessions/{session_id}/messages')
    def session_messages(session_id: str):
        history = store.history(session_id)
        if not history:
            raise HTTPException(404, detail='session not found')
        return {'session_id': session_id, 'messages': history}

    return app


app = create_app()
