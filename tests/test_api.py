import os
import tempfile
os.environ['WARMUP_ON_STARTUP']='false'
os.environ['TTS_ENABLED']='false'
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='mastercheb-api-test-')
os.environ['ADMIN_TOKEN']='test-only-token-with-at-least-32-characters'
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest
from app.main import app,active,rates,store
HEADERS={'origin':'http://127.0.0.1:5174'}
AUTH={'Authorization':'Bearer '+os.environ['ADMIN_TOKEN']}
HELLO={'event':'hello','language':'ru','consent':'2026-09-05'}
@pytest.fixture
def client():
 rates.clear();active.clear()
 with TestClient(app) as c: yield c

def test_private_endpoints(client):
 for url in ['/sessions','/knowledge/search?q=price']:
  assert client.get(url).status_code==401
 assert client.get('/sessions',headers=AUTH).status_code==200
 assert client.post('/admin/vad-settings').status_code in (404,405)
 assert client.get('/health').json()['text']

def test_origin_and_consent(client):
 with pytest.raises(WebSocketDisconnect):
  with client.websocket_connect('/ws',headers={'origin':'https://evil.example'}): pass
 with client.websocket_connect('/ws',headers=HEADERS) as ws:
  ws.send_json({'event':'hello','consent':False})
  with pytest.raises(WebSocketDisconnect):ws.receive_json()

def test_socket_validation_and_flow(client):
 with client.websocket_connect('/ws',headers=HEADERS) as ws:
  ws.send_json(HELLO)
  start=ws.receive_json(); assert start['event']=='session_started'
  sid=start['session_id']
  assert len(sid)==43
  assert ws.receive_json()['event']=='assistant_response'
  ws.send_json([]);assert ws.receive_json()['code']=='invalid'
  ws.send_text('bad json');assert ws.receive_json()['code']=='invalid'
  ws.send_json({'event':'user_text','text':'Сколько стоит?'})
  assert '50 000' in ws.receive_json()['text']
  ws.send_json({'event':'lead'})
  assert ws.receive_json()['stage']=='name'
  ws.send_json({'event':'user_text','text':'Test Person'})
  assert ws.receive_json()['lead']['name']=='Test Person'
 with client.websocket_connect('/ws',headers=HEADERS) as ws:
  ws.send_json({**HELLO,'session_id':sid})
  assert ws.receive_json()['lead']['name']=='Test Person'
  ws.send_json({'event':'ping'});assert ws.receive_json()['event']=='pong'
 assert client.patch('/sessions/'+sid,json={'status':'contacted'},headers=AUTH).status_code==200
 assert client.delete('/sessions/'+sid,headers=AUTH).status_code==200
 assert store.get(sid) is None

def test_duplicate_cannot_remove_original_session(client):
 with client.websocket_connect('/ws',headers=HEADERS) as a:
  a.send_json(HELLO);sid=a.receive_json()['session_id'];a.receive_json()
  with client.websocket_connect('/ws',headers=HEADERS) as b:
   b.send_json({**HELLO,'session_id':sid})
   with pytest.raises(WebSocketDisconnect):b.receive_json()
  assert sid in active
  a.send_json({'event':'ping'});assert a.receive_json()['event']=='pong'


def test_finish_voice_keeps_already_running_recognition(client, monkeypatch):
 import threading
 import app.main as backend
 entered, release = threading.Event(), threading.Event()
 class Segments:
  def __init__(self, *args): pass
  def accept_pcm16(self, pcm): return pcm
  def flush(self): return None
 def transcribe(pcm, language):
  entered.set()
  assert release.wait(5)
  return 'Сколько стоит?'
 monkeypatch.setattr(backend, 'VadSegmenter', Segments)
 monkeypatch.setitem(backend.ready, 'voice', True)
 monkeypatch.setattr(backend.stt, 'transcribe_pcm16', transcribe)
 try:
  with client.websocket_connect('/ws', headers=HEADERS) as ws:
   ws.send_json(HELLO); ws.receive_json(); ws.receive_json()
   ws.send_bytes(b'\x01\x00' * 4000)
   assert entered.wait(3)
   ws.send_json({'event':'finish_voice'})
   ws.send_json({'event':'ping'})
   events=[]
   while True:
    event=ws.receive_json()
    if event['event']=='pong': break
    events.append(event)
   release.set()
   assert not any(e.get('text')=='' for e in events)
   assert ws.receive_json()['text']=='Сколько стоит?'
   assert '50 000' in ws.receive_json()['text']
 finally:
  release.set()
