from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import secrets
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from time import monotonic
from typing import Literal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import settings
from .dialog import DialogManager, FIELDS, TEXT, valid_field
from .rag import RagKnowledgeBase
from .session_store import SessionStore
from .stt import WhisperStt
from .tts import SileroTts
from .tts_queue import TtsDeliveryQueue
from .vad import VadSegmenter, VadSettings

log = logging.getLogger("mastercheb")
store = SessionStore(settings.data_dir)
rag = RagKnowledgeBase(settings.rag_dir)
dialog = DialogManager(rag, store)
stt = WhisperStt(settings)
tts = SileroTts(settings)
delivery = TtsDeliveryQueue(tts)
ready = {'text': True, 'voice': False}
active: set[str] = set()
rates: dict[str, deque] = defaultdict(deque)
origins = os.getenv('ALLOWED_ORIGINS', 'https://mastercheb.ru,https://www.mastercheb.ru,http://localhost:5174,http://127.0.0.1:5174').split(',')
MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '8'))
CONSENT_VERSION = '2026-09-05'

def rate_limit(key, count=30, window=60):
    now = monotonic()
    q = rates[key]
    while q and now-q[0] > window:
        q.popleft()
    if len(q) >= count:
        return False
    q.append(now)
    if len(rates) > 2000:
        for old in list(rates):
            if not rates[old] or now-rates[old][-1] > window:
                rates.pop(old, None)
    return True

def warmup():
    try:
        stt.load()
        if settings.tts_enabled:
            tts.synthesize_wav('Здравствуйте, я Маша.')
        VadSegmenter(settings, VadSettings.from_settings(settings))
        ready['voice'] = True
    except Exception:
        log.exception('Voice unavailable; text service remains available')

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(asyncio.to_thread(warmup)) if settings.warmup_on_startup else None
    yield
    await delivery.shutdown()
    if task:
        with suppress(Exception):
            await task

app = FastAPI(title='МастерЧеб — Маша', lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Authorization','Content-Type'])

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response

def admin(authorization: str = Header(default='')):
    token = os.getenv('ADMIN_TOKEN', '')
    if len(token) < 24 or not secrets.compare_digest(authorization, 'Bearer ' + token):
        raise HTTPException(401, 'Unauthorized')

@app.get('/health')
async def health():
    return {'status':'ok', 'text':ready['text'], 'voice':ready['voice'], 'capacity_available': len(active) < MAX_CONNECTIONS}

@app.get('/company')
async def company():
    return json.loads(settings.company_config_path.read_text(encoding='utf-8'))

@app.get('/sessions', dependencies=[Depends(admin)])
async def sessions(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
    return {'sessions':store.list(limit, offset)}

class StatusPayload(BaseModel):
    status: Literal['new', 'contacted', 'completed']

@app.patch('/sessions/{sid}', dependencies=[Depends(admin)])
async def status(sid: str, payload: StatusPayload):
    session = store.get(sid)
    if not session:
        raise HTTPException(404)
    session['status'] = payload.status
    store.save(session)
    return {'ok':True}

@app.delete('/sessions/{sid}', dependencies=[Depends(admin)])
async def delete(sid: str):
    store.delete(sid)
    return {'ok':True}

@app.get('/knowledge/search', dependencies=[Depends(admin)])
async def search(q: str = Query(min_length=1, max_length=2000)):
    return {'matches':rag.search(q)}

@app.websocket('/ws')
async def websocket(ws: WebSocket):
    if ws.headers.get('origin') not in origins:
        await ws.close(code=1008)
        return
    if len(active) >= MAX_CONNECTIONS:
        await ws.close(code=1013)
        return
    ip = ws.client.host if ws.client else 'unknown'
    if not rate_limit('connect:'+ip, 20):
        await ws.close(code=1008)
        return
    await ws.accept()
    sid = None
    owns_session = False
    task = None
    epoch = 0
    use_voice = False
    segmenter = None
    audio_bytes = 0
    last_text = 0.0
    s = None

    async def cancel():
        nonlocal task, epoch
        epoch += 1
        if sid:
            await delivery.cancel_session(sid)
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        task = None

    async def emit(response):
        await ws.send_json(response)
        if use_voice and s['language']=='ru' and ready['voice']:
            await delivery.enqueue(sid, ws, response['text'])

    async def respond(text, action=None):
        nonlocal task
        await cancel()
        async def run():
            try:
                await emit(await dialog.process(s, text, action))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('Dialogue failed')
                with suppress(Exception):
                    await ws.send_json({'event':'error','code':'processing'})
        task = asyncio.create_task(run())

    async def recognize(pcm, current_epoch):
        if not pcm:
            await ws.send_json({'event':'stt_final', 'text':''})
            return
        text = await asyncio.to_thread(stt.transcribe_pcm16, pcm, s['language'])
        if current_epoch != epoch:
            return
        await ws.send_json({'event':'stt_final','text':text})
        if text:
            await emit(await dialog.process(s,text))

    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if not isinstance(hello,dict) or hello.get('event')!='hello' or hello.get('consent')!=CONSENT_VERSION:
            await ws.close(code=1008)
            return
        language = hello.get('language','ru')
        if language not in TEXT:
            await ws.close(code=1008)
            return
        resume = hello.get('session_id')
        if isinstance(resume,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',resume):
            s = store.get(resume)
        if s is None:
            s = store.create(language, CONSENT_VERSION)
        if s['id'] in active:
            await ws.close(code=1008)
            return
        sid = s['id']
        s['language'] = language
        active.add(sid)
        owns_session = True
        await ws.send_json({'event':'session_started','session_id':sid,'history':s['messages'],'lead':s['lead'],'stage':s['stage'],'submitted':s['submitted']})
        if not s['messages']:
            await emit(dialog.start(s))
        while True:
            message = await asyncio.wait_for(ws.receive(), timeout=180)
            if message['type']=='websocket.disconnect':
                break
            if message.get('bytes') is not None:
                pcm = message['bytes']
                if not ready['voice']:
                    await ws.send_json({'event':'error','code':'voice_unavailable'})
                    continue
                if len(pcm)>64000 or len(pcm)%2:
                    await ws.close(code=1009)
                    break
                audio_bytes += len(pcm)
                if audio_bytes > 16000*2*60:
                    await ws.send_json({'event':'error','code':'audio_limit'})
                    segmenter = None
                    audio_bytes = 0
                    continue
                if segmenter is None:
                    segmenter = VadSegmenter(settings, VadSettings.from_settings(settings))
                speech = segmenter.accept_pcm16(pcm)
                if speech:
                    audio_bytes = 0
                    await cancel()
                    task = asyncio.create_task(recognize(speech, epoch))
                continue
            raw = message.get('text','')
            if len(raw)>16000:
                await ws.close(code=1009)
                break
            try:
                p = json.loads(raw)
            except ValueError:
                await ws.send_json({'event':'error','code':'invalid'})
                continue
            if not isinstance(p,dict):
                await ws.send_json({'event':'error','code':'invalid'})
                continue
            event = p.get('event')
            if event=='ping':
                await ws.send_json({'event':'pong'})
            elif event=='voice_response_preference':
                use_voice = p.get('enabled') is True
                if not use_voice:
                    await delivery.cancel_session(sid)
            elif event=='barge_in':
                await cancel()
            elif event=='finish_voice':
                pcm = segmenter.flush() if segmenter else b''
                segmenter = None
                audio_bytes = 0
                if pcm:
                    await cancel()
                    task = asyncio.create_task(recognize(pcm,epoch))
                elif task is None or task.done():
                    await ws.send_json({'event':'stt_final', 'text':''})
                # Server endpointing may already have started recognition.
                # An empty browser flush must not cancel that utterance.
            elif event in ('user_text','lead','submit'):
                text = p.get('text','')
                if not isinstance(text,str) or len(text)>2000 or (event=='user_text' and not text.strip()):
                    await ws.send_json({'event':'error','code':'invalid'})
                    continue
                if not rate_limit('text:'+ip,60) or len(s['messages']) >= 1000:
                    await ws.send_json({'event':'error','code':'rate_limit'})
                    continue
                await respond(text, event if event!='user_text' else None)
            else:
                await ws.send_json({'event':'error','code':'invalid'})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception:
        log.exception('WebSocket failed')
    finally:
        await cancel()
        if owns_session and sid and sid in active and s is not None:
            active.discard(sid)
            await delivery.close_session(sid)

if settings.static_dir.exists():
    app.mount('/', StaticFiles(directory=settings.static_dir, html=True), name='site')
