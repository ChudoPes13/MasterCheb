"""Local structured dialogue planner. Commercial facts are rendered by the app."""
import asyncio
import json
import logging
import re
from time import monotonic
from urllib.parse import urlparse
import httpx
from .config import settings

log = logging.getLogger(__name__)

class LlmClient:
    def __init__(self):
        self.base = settings.llama_base_url.rstrip('/')
        if urlparse(self.base).hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('The demo requires a local LLM endpoint')
        self.slots = asyncio.Semaphore(3)
        self.retry_after = 0

    async def health(self):
        try:
            async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
                return (await client.get(self.base + '/models')).status_code == 200
        except httpx.HTTPError:
            return False

    async def plan(self, session, text, chunks):
        if monotonic() < self.retry_after:
            return None
        ids = [c['id'] for c in chunks]
        kinds = ['answer', 'lead', 'cancel']
        question = bool(re.search(r'[?？]', text) or re.match(r'(?i)^(а |как\b|сколько\b|что\b|какие\b|можно\b|how\b|what\b|can\b|do\b|多少|可以|怎么)', text.strip()))
        if session.get('stage') in ('name', 'company', 'industry', 'task', 'contact', 'time') and not question:
            kinds.append('field')
        schema = {'type': 'object', 'properties': {
            'kind': {'type': 'string', 'enum': kinds},
            'topics': {'type': 'array', 'items': {'type': 'string', 'enum': ids}, 'maxItems': 1},
            'answer': {'type': 'string'},
            'next': {'type': 'string', 'enum': ['none', 'example', 'task', 'channel', 'invite']},
            'value': {'type': 'string'}},
            'required': ['kind', 'topics', 'answer', 'next', 'value'], 'additionalProperties': False}
        # One source of truth; compact summaries route questions, full answers stay in RAG.
        facts = '\n'.join(c['id'] + ': ' + c['title'] + '. ' + c['answers']['ru'].split('. ')[0] for c in chunks)
        system = (settings.config_dir / 'masha_scenario.txt').read_text(encoding='utf-8')
        state = {k: session.get(k) for k in ('language', 'stage', 'last_topic', 'asked', 'declined')}
        history = [{'role': m['role'], 'content': m['text'][:400]} for m in session['messages'][-5:]]
        if history and history[-1]['role'] == 'user':
            history.pop()
        # Mistral's chat template requires user/assistant alternation; the site
        # greeting has no preceding user message and belongs outside this history.
        while history and history[0]['role'] != 'user':
            history.pop(0)
        payload = {'model': settings.llama_model, 'messages': [
            {'role': 'system', 'content': system + '\nFACTS:\n' + facts + '\nSTATE: ' + json.dumps(state, ensure_ascii=False)},
            {'role': 'user', 'content': 'HISTORY (context only):\n' + json.dumps(history, ensure_ascii=False) + '\nCURRENT (answer this):\n' + text}],
            'response_format': {'type': 'json_object', 'schema': schema},
            'temperature': 0.15, 'top_p': 0.9, 'max_tokens': 280, 'cache_prompt': True}
        try:
            async with self.slots, httpx.AsyncClient(timeout=settings.llama_timeout_sec, trust_env=False) as client:
                response = await client.post(self.base + '/chat/completions', json=payload)
                response.raise_for_status()
                result = json.loads(response.json()['choices'][0]['message']['content'])
            if (not isinstance(result, dict) or result.get('kind') not in schema['properties']['kind']['enum']
                or result.get('next') not in schema['properties']['next']['enum']
                or not isinstance(result.get('topics'), list) or len(result['topics']) > 2
                or any(t not in ids for t in result['topics'])
                or not isinstance(result.get('answer'), str) or len(result['answer']) > 700
                or not isinstance(result.get('value'), str)):
                return None
            return result
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            self.retry_after = monotonic() + 10
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            log.warning('Local dialogue planner unavailable (%s); using approved FAQ fallback', status)
            return None
