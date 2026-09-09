import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, Square, Volume2, MessageCircle, RotateCcw, ArrowUpRight } from "lucide-react";
import { Copy, Lang } from "./i18n";
export const API = import.meta.env.VITE_API_BASE ?? (location.hostname === "localhost" || location.hostname === "127.0.0.1" ? location.origin : "https://api.mastercheb.ru");
type Message = {role:string;text:string};
const keys = ["name","company","industry","task","contact","time"];
export function ContactLinks({t}:{t:Copy}) {return <div className="contact-links"><a href="https://t.me/mastercheb" target="_blank" rel="noreferrer">{t.telegram}<ArrowUpRight size={17}/></a><a href="mailto:pochtaeto@gmail.com">{t.email}<ArrowUpRight size={17}/></a><a href="tel:+79176693889">{t.phone}<ArrowUpRight size={17}/></a></div>}
export function Chat({lang,t,online,voiceReady}:{lang:Lang;t:Copy;online:boolean|null;voiceReady:boolean}) {
 const [connected,setConnected]=useState(false), [consent,setConsent]=useState(false),[messages,setMessages]=useState<Message[]>([]),[input,setInput]=useState(""),[sound,setSound]=useState(true),[mode,setMode]=useState("text"),[recording,setRecording]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[lead,setLead]=useState<Record<string,string>>({}),[stage,setStage]=useState<string|null>(null),[submitted,setSubmitted]=useState(false),[speaking,setSpeaking]=useState(false),[position,setPosition]=useState(0);
 const ws=useRef<WebSocket|null>(null), scroller=useRef<HTMLDivElement>(null), stream=useRef<MediaStream|null>(null), ctx=useRef<AudioContext|null>(null), node=useRef<AudioWorkletNode|null>(null), recordingRef=useRef(false), audio=useRef<HTMLAudioElement|null>(null), queue=useRef<Blob[]>([]), soundRef=useRef(true), playEpoch=useRef(0), closing=useRef(false), started=useRef(0), timer=useRef<number|undefined>(undefined);
 const turn=useRef(""), delivered=useRef(false), nativeSpeaking=useRef(false), acceptAudio=useRef(false), pcmBuffer=useRef<number[]>([]);
 function acknowledge(){if(turn.current&&delivered.current&&!audio.current&&!queue.current.length&&!nativeSpeaking.current&&ws.current?.readyState===1){ws.current.send(JSON.stringify({event:"playback_done",turn_id:turn.current}));turn.current=""}}
 function stopPlayback(){playEpoch.current++;acceptAudio.current=false;queue.current=[];if(audio.current){audio.current.onended=null;audio.current.onerror=null;audio.current.pause();URL.revokeObjectURL(audio.current.src);audio.current=null;}nativeSpeaking.current=false;window.speechSynthesis?.cancel();setSpeaking(false);acknowledge()}
 function playNext(){if(audio.current||!soundRef.current)return;if(!queue.current.length){acknowledge();return}const b=queue.current.shift()!;const a=new Audio(URL.createObjectURL(b));const version=playEpoch.current;audio.current=a;setSpeaking(true);const finish=(failed=false)=>{URL.revokeObjectURL(a.src);if(version!==playEpoch.current||audio.current!==a)return;audio.current=null;setSpeaking(false);if(failed)setError(t.voiceError);playNext()};a.onended=()=>finish();a.onerror=()=>finish(true);a.play().catch(()=>finish(true))}
 function flushPcm(){const buffer=pcmBuffer.current;pcmBuffer.current=[];if(!buffer.length||ws.current?.readyState!==1)return;const pcm=new Int16Array(buffer.length);for(let i=0;i<buffer.length;i++)pcm[i]=Math.max(-32768,Math.min(32767,buffer[i]*32768));ws.current.send(pcm.buffer)}
 function stopMic(send=true){if(!recordingRef.current)return;recordingRef.current=false;setRecording(false);window.clearTimeout(timer.current);if(send)flushPcm();else pcmBuffer.current=[];node.current?.disconnect();node.current=null;stream.current?.getTracks().forEach(tr=>tr.stop());stream.current=null;void ctx.current?.close();ctx.current=null;if(send&&ws.current?.readyState===1){ws.current.send(JSON.stringify({event:"finish_voice"}));setBusy(true)}}
 function send(text:string,event="user_text"){if(ws.current?.readyState!==1)return;stopMic(false);stopPlayback();setError("");if(event==="user_text"){setMessages(m=>[...m,{role:"user",text}]);setInput("")}setBusy(true);ws.current.send(JSON.stringify({event,text}))}
 function connect(){
  if(!consent||online!==true||ws.current?.readyState===0||ws.current?.readyState===1)return;
  closing.current=false;setError("");setBusy(true);
  const socket=new WebSocket(API.replace(/^http/,"ws")+"/ws");ws.current=socket;
  socket.onopen=()=>socket.send(JSON.stringify({event:"hello",protocol:2,voice_response:soundRef.current,language:lang,consent:"2026-09-05",session_id:sessionStorage.getItem("mastercheb-session-"+lang)}));
  socket.onmessage=e=>{
   if(e.data instanceof Blob){if(soundRef.current&&acceptAudio.current){queue.current.push(e.data);playNext()}return}
   let p;try{p=JSON.parse(e.data)}catch{return}
   if(p.event==="turn_status"){if(p.state==="queued"){setPosition(p.position);setBusy(true)}else if(p.state==="processing"){setPosition(0);turn.current=p.turn_id;delivered.current=false;acceptAudio.current=true;setBusy(true)}else if(p.state==="idle"){setPosition(0);setBusy(false)}return}
   if(p.event==="audio_delivery_complete"){if(p.turn_id===turn.current){delivered.current=true;acknowledge()}return}
   if(p.event==="session_started"){setConnected(true);setBusy(false);sessionStorage.setItem("mastercheb-session-"+lang,p.session_id);setMessages(p.history??[]);setLead(p.lead??{});setStage(p.stage);setSubmitted(p.submitted);socket.send(JSON.stringify({event:"voice_response_preference",enabled:soundRef.current}))}
   if(p.event==="assistant_response"){setBusy(false);setMessages(m=>[...m,{role:"assistant",text:p.text}]);setLead(p.lead);setStage(p.stage);setSubmitted(p.submitted);
    if(lang!=="ru"&&soundRef.current&&"speechSynthesis" in window){const voices=speechSynthesis.getVoices();const voice=voices.find(v=>v.lang.startsWith(lang==="zh"?"zh":"en"));if(voice){const u=new SpeechSynthesisUtterance(p.text);const version=playEpoch.current;nativeSpeaking.current=true;u.voice=voice;u.lang=lang==="zh"?"zh-CN":"en-US";u.onstart=()=>setSpeaking(true);const finish=()=>{if(version!==playEpoch.current)return;nativeSpeaking.current=false;setSpeaking(false);acknowledge()};u.onend=finish;u.onerror=()=>{finish();setError(t.voiceError)};speechSynthesis.speak(u)}else setError(t.localVoice)}
   }
   if(p.event==="stt_final"){stopMic(false);if(p.text){setMessages(m=>[...m,{role:"user",text:p.text}]);setBusy(true)}else setBusy(false)}
   if(p.event==="error"||p.event==="tts_error"){setBusy(false);setPosition(0);setError(p.code==="queue_timeout"?(lang==="ru"?"Сейчас много обращений. Попробуйте снова чуть позже или напишите Александру.":lang==="en"?"Demand is high. Please retry shortly or contact Alexander.":"当前咨询较多，请稍后重试或联系亚历山大。"):p.code==="voice_unavailable"||p.event==="tts_error"?t.voiceError:t.error);stopMic(false)}
  };
  socket.onerror=()=>{setError(t.error);setBusy(false)};
  socket.onclose=()=>{setConnected(false);setBusy(false);stopMic(false);stopPlayback();if(!closing.current)setError(t.error)};
 }
 async function startMic(){
  if(!connected||!voiceReady)return;
  stopPlayback();ws.current?.send(JSON.stringify({event:"barge_in"}));setError("");
  try{
   const media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
   stream.current=media;
   const context=new AudioContext({sampleRate:16000});ctx.current=context;await context.resume();await context.audioWorklet.addModule("/audio-processor.worklet.js");
   const source=context.createMediaStreamSource(media), processor=new AudioWorkletNode(context,"mastercheb-audio-processor");node.current=processor;
   const mute=context.createGain();mute.gain.value=0;source.connect(processor);processor.connect(mute);mute.connect(context.destination);
   pcmBuffer.current=[];let heard=false;let lastVoice=performance.now();started.current=performance.now();recordingRef.current=true;setRecording(true);setBusy(false);
   processor.port.onmessage=({data})=>{
    if(!recordingRef.current)return;
    if(data.rms>.012){heard=true;lastVoice=performance.now()}
    const samples:Float32Array=data.samples;for(let i=0;i<samples.length;i++)pcmBuffer.current.push(samples[i]);
    if(pcmBuffer.current.length>=3200)flushPcm();
    if(heard&&performance.now()-lastVoice>800)stopMic();
   };
   timer.current=window.setTimeout(()=>stopMic(),55000);
  }catch{stream.current?.getTracks().forEach(tr=>tr.stop());stream.current=null;void ctx.current?.close();ctx.current=null;setError(t.voiceError);setRecording(false);recordingRef.current=false}
 }
 function newConversation(){closing.current=true;stopMic(false);stopPlayback();ws.current?.close();ws.current=null;sessionStorage.removeItem("mastercheb-session-"+lang);setMessages([]);setLead({});setStage(null);setSubmitted(false);setConnected(false);setError("")}
 useEffect(()=>{scroller.current?.scrollTo({top:scroller.current.scrollHeight,behavior:"smooth"})},[messages,busy]);
 useEffect(()=>{return ()=>{closing.current=true;stopMic(false);stopPlayback();ws.current?.close()}},[]);
 useEffect(()=>{const heartbeat=window.setInterval(()=>{if(ws.current?.readyState===1)ws.current.send(JSON.stringify({event:"ping"}))},25000);return()=>window.clearInterval(heartbeat)},[]);
 useEffect(()=>{soundRef.current=sound;ws.current?.readyState===1&&ws.current.send(JSON.stringify({event:"voice_response_preference",enabled:sound}));if(!sound)stopPlayback()},[sound]);
 return <div className="chat-card" id="chat">
  <div className="chat-heading"><div className="avatar mini">м<span/></div><div><strong>{t.masha}</strong><small>{t.role}</small></div><span className={"status "+(online?"is-online":"")}>{online===null?t.checking:online?t.online:t.offline}</span></div>
  {online===false&&!connected?<div className="offline-state"><div className="orb small-orb"><span/></div><h3>{t.offline}</h3><p>{t.offlineText}</p><ContactLinks t={t}/></div>:!connected?<div className="chat-welcome"><div className="orb small-orb"><span/></div><h3>{t.accent}</h3><p>{t.demoIntro}</p><label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/><span>{t.consent}. <a href={"?page=privacy&lang="+lang} target="_blank">{t.policy}</a></span></label><button className="button primary" disabled={!consent||!online||busy} onClick={connect}>{busy?t.checking:t.connect}<ArrowUpRight size={18}/></button></div>:<>
  <div className="chat-messages" ref={scroller} role="log" aria-live="polite">{messages.map((m,i)=><div key={i} className={"message "+m.role}>{m.role==="assistant"&&<span className="message-label">{t.masha}</span>}<p>{m.text}</p></div>)}{busy&&<div className="message assistant pending">{position?(lang==="ru"?`Вы в очереди: ${position}. Ждём завершения текущих ответов.`:lang==="en"?`Queue position: ${position}. Waiting for current replies to finish.`:`排队位置：${position}，正在等待当前回复结束。`):t.thinking}</div>}</div>
  {position>0&&<button className="speech-status" onClick={()=>{ws.current?.send(JSON.stringify({event:"barge_in"}));setPosition(0);setBusy(false)}}>{lang==="ru"?"Отменить ожидание":lang==="en"?"Leave queue":"取消等待"}</button>}
  {stage==="confirm"&&<div className="lead-review"><strong>{t.confirmTitle}</strong><dl>{keys.map((k,i)=><div key={k}><dt>{t.labels[i]}</dt><dd>{lead[k]}</dd></div>)}</dl><button className="button primary" disabled={busy} onClick={()=>send("","submit")}>{t.submit}</button></div>}
  <div className="chat-actions">{messages.length<4&&t.questionChips.map(q=><button key={q} onClick={()=>send(q)} disabled={busy}>{q}</button>)}<button onClick={()=>send("","lead")} disabled={busy}>{submitted?t.sent:t.lead}</button><button title={t.reset} onClick={newConversation}><RotateCcw size={14}/></button></div>
  <div className="mode-row"><div className="segmented" aria-label={t.modes}><button className={mode==="text"?"selected":""} onClick={()=>{stopMic();setMode("text")}}><MessageCircle size={15}/>{t.typing}</button><button className={mode==="voice"?"selected":""} onClick={()=>setMode("voice")}><Mic size={15}/>{t.voice}</button></div><label className="sound-toggle"><input type="checkbox" checked={sound} onChange={e=>setSound(e.target.checked)}/><Volume2 size={15}/>{t.sound}</label></div>
  {mode==="text"?<form className="chat-input" onSubmit={e=>{e.preventDefault();if(input.trim())send(input.trim())}}><input aria-label={t.typing} value={input} maxLength={2000} placeholder={t.placeholder} onChange={e=>setInput(e.target.value)}/><button aria-label={t.send} disabled={!input.trim()}><ArrowUp size={20}/></button></form>:<button className={"mic-button "+(recording?"recording":"")} disabled={!voiceReady} onClick={()=>recording?stopMic():void startMic()}>{recording?<Square size={19}/>:<Mic size={19}/>} {recording?t.stop:t.speak}</button>}
  {(recording||speaking)&&<button className="speech-status" onClick={()=>{stopPlayback();ws.current?.send(JSON.stringify({event:"barge_in"}))}}>{recording?t.listening:t.stopAudio}</button>}
  {lang!=="ru"&&sound&&<small className="voice-note">{t.localVoice}</small>}
  </>}
  {error&&<p className="error" role="alert">{error} {!connected&&<a href="#contact">{t.consult}</a>}</p>}
 </div>
}
