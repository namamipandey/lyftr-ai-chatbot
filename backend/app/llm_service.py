"""LiteLLM-backed gateway with explicit cache hit reporting and deterministic key failover.

LiteLLM's built-in Cache backend is used, rather than a separate application cache.
Cache identity is independent of session IDs and API key IDs.
"""
import hashlib
import json
import logging
import threading
import time

import litellm
from litellm.caching import Cache

logger = logging.getLogger(__name__)


class AllProvidersUnavailable(Exception):
    pass


class Gateway:
    def __init__(self, settings):
        self.settings = settings
        self.cache = Cache(type='local')
        self.lock = threading.RLock()

    def cache_key(self, messages):
        payload = json.dumps({'model': self.settings.model, 'messages': messages}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _read_cache(self, key):
        with self.lock:
            return self.cache.get_cache(cache_key=key)

    def _write_cache(self, key, record):
        with self.lock:
            self.cache.add_cache(record, cache_key=key)

    @staticmethod
    def parse_simulation(header):
        rules = {}
        for item in (header or '').split(','):
            if not item.strip():
                continue
            try:
                key, code = item.strip().split('=', 1)
                if key.strip() and int(code) in (429, 500, 502, 503):
                    rules[key.strip()] = int(code)
            except (ValueError, TypeError):
                continue
        return rules

    @staticmethod
    def retryable(error):
        status = getattr(error, 'status_code', None)
        if status in (429, 500, 502, 503, 504):
            return True
        name = type(error).__name__.lower()
        return any(x in name for x in ('ratelimit', 'serviceunavailable', 'internalserver', 'apiconnection', 'timeout', 'quota'))

    def answer(self, messages, failure_header=None):
        start = time.perf_counter()
        key = self.cache_key(messages)
        cached = self._read_cache(key)
        if cached is not None:
            # Cache implementations can return a serialized record.
            if isinstance(cached, str):
                cached = json.loads(cached)
            metadata = {
                'resolution_source': 'LLM_CACHE', 'model': cached['model'],
                'latency_ms': max(0, int((time.perf_counter()-start)*1000)),
                'input_tokens': cached['input_tokens'], 'output_tokens': cached['output_tokens'],
                'key_id': None, 'fallback_attempts': 0,
            }
            return cached['reply'], metadata

        rules = self.parse_simulation(failure_header) if self.settings.simulate else {}
        failures = 0
        for idx, api_key in enumerate(self.settings.keys, 1):
            key_id = f'key_{idx}'
            if key_id in rules or '*' in rules:
                failures += 1
                continue
            try:
                response = litellm.completion(
                    model=self.settings.model, messages=messages, api_key=api_key,
                    timeout=30, num_retries=0, caching=False,
                )
                reply = response.choices[0].message.content
                if not isinstance(reply, str) or not reply.strip():
                    raise ValueError('Model returned an empty answer')
                usage = response.usage
                record = {
                    'reply': reply, 'model': self.settings.model,
                    'input_tokens': int(usage.prompt_tokens),
                    'output_tokens': int(usage.completion_tokens),
                }
                try:
                    self._write_cache(key, record)
                except Exception:
                    logger.exception('Cache write failed')
                metadata = {
                    'resolution_source': 'LIVE_INFERENCE', 'model': self.settings.model,
                    'latency_ms': max(0, int((time.perf_counter()-start)*1000)),
                    'input_tokens': record['input_tokens'], 'output_tokens': record['output_tokens'],
                    'key_id': key_id, 'fallback_attempts': failures,
                }
                return reply, metadata
            except Exception as exc:
                if not self.retryable(exc):
                    logger.warning('Provider returned non-retryable error: %s', type(exc).__name__)
                    raise
                logger.warning('Provider %s failed with %s', key_id, type(exc).__name__)
                failures += 1
        raise AllProvidersUnavailable()
