"""Integration checks against a running local backend, using synthetic test conversations."""
import asyncio,json,time,wave,io,os,statistics
from pathlib import Path
import httpx,numpy as np,websockets

async def connect(lang='ru'):
    ws=await websockets.connect('ws://127.0.0.1:8001/ws',origin='http://127.0.0.1:5174',max_size=8_000_000)
    await ws.send(json.dumps({'event':'hello','language':lang,'consent':'2026-09-05'}))
    start=json.loads(await ws.recv());await ws.recv()
    return ws,start['session_id']

async def text_user(i):
    ws,sid=await connect(['ru','en','zh'][i%3])
    question=['Сколько стоит внедрение?','How much does it cost?','费用是多少？'][i%3]
    start=time.perf_counter()
    await ws.send(json.dumps({'event':'user_text','text':question}))
    answer=json.loads(await ws.recv())
    elapsed=time.perf_counter()-start
    assert '50' in answer['text']
    await ws.close()
    return {'session':sid,'text_seconds':elapsed}

async def main():
    results=await asyncio.gather(*(text_user(i) for i in range(8)))
    from app.tts import SileroTts
    from app.config import settings
    synth=SileroTts(settings)
    wav=await asyncio.to_thread(synth.synthesize_wav,'Сколько стоит внедрение?')
    with wave.open(io.BytesIO(wav)) as w:
        pcm=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16)
        samples=np.interp(np.arange(0,len(pcm),w.getframerate()/16000),np.arange(len(pcm)),pcm).astype('<i2').tobytes()
    ws,sid=await connect()
    await ws.send(json.dumps({'event':'voice_response_preference','enabled':True}))
    start=time.perf_counter()
    for pos in range(0,len(samples),6400):
        await ws.send(samples[pos:pos+6400])
    await ws.send(json.dumps({'event':'finish_voice'}))
    events=[];audio_chunks=0
    async with asyncio.timeout(60):
        while True:
            event=await ws.recv()
            if isinstance(event,bytes):
                assert event[:4]==b'RIFF'
                audio_chunks+=1;continue
            data=json.loads(event)
            events.append({'event':data['event'],'seconds':time.perf_counter()-start,'text':data.get('text')})
            if data['event']=='assistant_tts_end' and data['chunk_index']==data['chunk_count']:
                break
    await ws.close()
    assert any(e['event']=='stt_final' and 'стоит' in (e['text'] or '').lower() for e in events)
    assert any(e['event']=='assistant_response' and '50 000' in e['text'] for e in events)
    assert audio_chunks>0
    report={'concurrency':8,'text_median_seconds':statistics.median(r['text_seconds'] for r in results),'text_max_seconds':max(r['text_seconds'] for r in results),'voice':events,'audio_chunks':audio_chunks}
    Path('output').mkdir(exist_ok=True)
    Path('output/live-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    from dotenv import dotenv_values
    token=dotenv_values('.env')['ADMIN_TOKEN']
    async with httpx.AsyncClient(trust_env=False) as client:
        for session in [r['session'] for r in results]+[sid]:
            await client.delete('http://127.0.0.1:8001/sessions/'+session,headers={'Authorization':'Bearer '+token})
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':asyncio.run(main())
