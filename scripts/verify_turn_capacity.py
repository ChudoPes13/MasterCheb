"""Exercise only synthetic sessions; discard received audio after measuring it."""
import asyncio
import io
import json
import wave
import argparse
from pathlib import Path
from time import monotonic
import websockets
from app.config import settings
from app.session_store import SessionStore

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--with-stt',action='store_true')
    args=parser.parse_args()
    sockets=[]; ids=[]; results=[]
    async def receive_complete(ws):
        start=monotonic(); duration=0; chunks=0; token=None; answer=''; recognized=False
        while True:
            event=await asyncio.wait_for(ws.recv(),60)
            if isinstance(event,bytes):
                with wave.open(io.BytesIO(event)) as wav:
                    duration+=wav.getnframes()/wav.getframerate();chunks+=1
                continue
            event=json.loads(event)
            if event['event']=='session_started': ids.append(event['session_id'])
            if event['event']=='turn_status' and event['state']=='processing': token=event['turn_id']
            if event['event']=='assistant_response': answer=event['text']
            if event['event']=='stt_final': recognized=bool(event['text'])
            if event['event'] in ('error','tts_error'): raise AssertionError(event)
            if event['event']=='audio_delivery_complete':
                assert event['turn_id']==token and chunks>0 and duration>0
                results.append({'delivery_seconds':round(monotonic()-start,2),'audio_seconds':round(duration,2),'chunks':chunks,'recognized':recognized})
                return token,answer
    async def ack(ws,token):
        await ws.send(json.dumps({'event':'playback_done','turn_id':token}))
        assert json.loads(await ws.recv())['state']=='idle'
    try:
        for _ in range(4):
            sockets.append(await websockets.connect('ws://127.0.0.1:8001/ws',origin='http://127.0.0.1:5174',max_size=8_000_000))
        hello={'event':'hello','protocol':2,'voice_response':True,'language':'ru','consent':'2026-09-05'}
        for ws in sockets[:3]: await ws.send(json.dumps(hello))
        first=await asyncio.gather(*(receive_complete(ws) for ws in sockets[:3]))
        await sockets[3].send(json.dumps(hello))
        event=json.loads(await sockets[3].recv());ids.append(event['session_id'])
        queued=json.loads(await sockets[3].recv());assert queued['state']=='queued' and queued['position']==1
        await ack(sockets[0],first[0][0])
        fourth=await receive_complete(sockets[3])
        await asyncio.gather(ack(sockets[1],first[1][0]),ack(sockets[2],first[2][0]),ack(sockets[3],fourth[0]))
        questions=['Сколько стоит?','Есть реальные клиенты?','Прайс на тысячу страниц загрузите?']
        for ws,text in zip(sockets[:3],questions):
            await ws.send(json.dumps({'event':'user_text','text':text},ensure_ascii=False))
        answers=await asyncio.gather(*(receive_complete(ws) for ws in sockets[:3]))
        assert '50 000' in answers[0][1]
        assert 'внедрена' in answers[1][1]
        assert 'тысячи' in answers[2][1]
        await asyncio.gather(*(ack(ws,turn[0]) for ws,turn in zip(sockets[:3],answers)))
        if args.with_stt:
            # Public synthetic phrase, never a visitor recording.
            import numpy as np
            with wave.open(str(Path('output/pronunciation-audit/dialog-name.wav'))) as wav:
                assert wav.getframerate()==48000 and wav.getnchannels()==1
                pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')[::3].tobytes()
            for ws in sockets[:3]:
                for offset in range(0,len(pcm),6400): await ws.send(pcm[offset:offset+6400])
                await ws.send(json.dumps({'event':'finish_voice'}))
            spoken=await asyncio.gather(*(receive_complete(ws) for ws in sockets[:3]))
            assert all(r['recognized'] for r in results[-3:])
            await asyncio.gather(*(ack(ws,turn[0]) for ws,turn in zip(sockets[:3],spoken)))
        print(json.dumps({'three_parallel':True,'fourth_queued_until_playback_ack':True,'turns':results}))
    finally:
        await asyncio.gather(*(ws.close() for ws in sockets))
        # Delete only IDs created above, never inspect other sessions.
        store=SessionStore(settings.data_dir)
        for sid in ids: store.delete(sid)

if __name__=='__main__': asyncio.run(main())
