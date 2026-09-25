import React,{useEffect,useRef,useState} from 'react';
import Markdown from 'react-markdown';
import {ArrowLeft,Bot,CheckCircle2,ChevronRight,MessageSquare,RefreshCw,Send,Square,X} from 'lucide-react';
import './workers-panel.css';
type Data=Record<string,any>;
type WorkerMessage={id?:string;messageId?:string;role:string;text:string};
export default function WorkersPanel({team,connected,onData,selectedThread,onBackToChat}:{team:string;connected:boolean;onData?:(value:Data)=>void;selectedThread?:string;onBackToChat?:()=>void}){
  const [data,setData]=useState<Data>({workers:[]}),[error,setError]=useState(''),[busy,setBusy]=useState(false),[selected,setSelected]=useState(''),[receipt,setReceipt]=useState('');
  const [conversation,setConversation]=useState<Data|null>(null),[conversationBusy,setConversationBusy]=useState(false),[conversationError,setConversationError]=useState(''),[chatError,setChatError]=useState(''),[chatReceipt,setChatReceipt]=useState('');
  const [messageDrafts,setMessageDrafts]=useState<Record<string,string>>({}),[reportDrafts,setReportDrafts]=useState<Record<string,string>>({});
  const generation=useRef(0),conversationGeneration=useRef(0),conversationSeq=useRef(0),history=useRef<HTMLDivElement>(null),follow=useRef(true);
  useEffect(()=>{generation.current++;setData({workers:[]});setSelected('');setReceipt('');setError('');void refresh();const timer=setInterval(()=>{if(connected)void refresh()},30000);return()=>{generation.current++;clearInterval(timer)}},[team,connected]);
  useEffect(()=>{if(selectedThread)setSelected(selectedThread)},[selectedThread]);
  useEffect(()=>{
    conversationGeneration.current++;follow.current=true;
    setConversation(null);setConversationError('');setConversationBusy(false);setChatError('');setChatReceipt('');
    if(!selected)return;
    void loadConversation(selected,true);
    if(!connected)return;
    const timer=setInterval(()=>{if(!document.hidden)void loadConversation(selected)},5000);
    return()=>{conversationGeneration.current++;clearInterval(timer)};
  },[selected,connected,team]);
  useEffect(()=>{if(follow.current&&history.current)history.current.scrollTop=history.current.scrollHeight;},[conversation,selected]);
  async function call(action:string,body?:Data){const r=await fetch(`/api/runtime/${encodeURIComponent(team)}/${action}`,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const value=await r.json();if(!r.ok)throw Error(value.error||'Worker operation failed.');return value}
  async function refresh(){const current=generation.current;setBusy(true);try{const value=await call('workers');if(current!==generation.current)return;setData(value);onData?.(value);setError('')}catch(e:any){if(current===generation.current)setError(e.message)}finally{if(current===generation.current)setBusy(false)}}
  async function loadConversation(threadId:string,manual=false){
    const current=conversationGeneration.current,seq=++conversationSeq.current;
    if(manual)setConversationBusy(true);
    try{
      const value=await call(`worker-conversation?threadId=${encodeURIComponent(threadId)}`);
      if(current!==conversationGeneration.current||seq!==conversationSeq.current)return;
      setConversation(value);setConversationError('');
    }catch(e:any){
      if(current===conversationGeneration.current&&seq===conversationSeq.current)setConversationError(e.message);
    }finally{
      if(manual)setConversationBusy(false);
    }
  }
  async function send(e:React.FormEvent){e.preventDefault();const threadId=selected,text=messageDrafts[threadId]||'';setBusy(true);setChatError('');setChatReceipt('');try{const r=await call('worker-message',{threadId,prompt:text});setMessageDrafts(old=>({...old,[threadId]:''}));setChatReceipt(`Submitted to the native worker (${r.mode==='turn/steer'?'active work updated':'worker continued'}). Its next reply appears in the history above.`);void loadConversation(threadId)}catch(e:any){setChatError(e.message)}finally{setBusy(false)}}
  async function report(e:React.FormEvent){e.preventDefault();const threadId=selected,text=reportDrafts[threadId]||'';setBusy(true);setChatError('');setChatReceipt('');try{await call('worker-report',{threadId,summary:text});setReportDrafts(old=>({...old,[threadId]:''}));setChatReceipt('Report submitted to the main supervisor conversation. The worker has not confirmed this summary; open the main conversation to see the supervisor act on it.')}catch(e:any){setChatError(e.message)}finally{setBusy(false)}}
  async function stop(){setBusy(true);try{const r=await call('stop-workers',{});setReceipt(`${r.results.filter((x:Data)=>x.status==='stopRequested').length} stop requests sent. Refresh to check which workers stopped.`);setError('')}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  const workers=data.workers||[]; const canControl=data.workerControl===true;
  const selectedWorker=workers.find((w:Data)=>w.threadId===selected);
  const selectedName=selectedWorker?(selectedWorker.nickname||selectedWorker.role||'Worker'):'Worker';
  const conversationAvailable=conversation?.conversationAvailable===true;
  const conversationMessages:WorkerMessage[]=Array.isArray(conversation?.messages)?conversation.messages:[];
  const unavailableReason=conversation?(conversation.reason||conversation.error||''):'';
  const label=(id:string)=>workers.find((w:Data)=>w.threadId===id)?.nickname||workers.find((w:Data)=>w.threadId===id)?.role||'Supervisor';
  const markdown={a:({children,...props}:any)=><a {...props} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt}:any)=><span>{alt?`[Image: ${alt}]`:'[Image]'}</span>};
  return <section className="workers-panel"><header><div><span className="usage-kicker">LIVE RUNTIME</span><h3>Talk to your team</h3><p>Follow the observed team. Available controls depend on the provider.</p></div><button className="small-button" disabled={!connected||busy} onClick={refresh}><RefreshCw size={14}/>Refresh workers</button></header>
  {error&&<p role="alert" className="workers-error">{error}</p>}{receipt&&<p role="status" className="workers-receipt">{receipt}</p>}
  {!workers.length?<p className="workers-empty">{data.error?data.error:connected?'Workers appear after the supervisor delegates. Refresh to read the native roster.':'Connect this chat to see its active team.'}</p>:<><div className="worker-cards">{workers.map((w:Data)=><button key={w.threadId} className={selected===w.threadId?'selected':''} aria-pressed={selected===w.threadId} onClick={()=>{setSelected(w.threadId);setReceipt('');setChatError('');setChatReceipt('')}}><span className="worker-avatar"><Bot size={20}/></span><span><b>{w.nickname||w.role||'Worker'}</b>{w.model&&<small>{w.model}</small>}{typeof w.usageSummary?.totalTokens==='number'&&<small>{w.usageSummary.totalTokens.toLocaleString()} reported tokens · individual allowance not reported</small>}<small>{label(w.parentThreadId)}<ChevronRight size={11}/>{w.role||'Specialist'}</small></span><i className={`worker-state ${w.status}`}>{w.stale?'Needs refresh':w.status||'Unknown'}</i></button>)}</div><div className="workers-actions">{canControl&&<button className="small-button" onClick={stop} disabled={busy||!connected}><Square size={12}/>Stop observed workers</button>}{!data.complete&&<small>Some descendants could not be verified.</small>}</div></>}
  {selected&&<div className="worker-subchat" aria-label={`Focused conversation with ${selectedName}`}>
    <header className="subchat-header">
      <nav className="subchat-breadcrumb" aria-label="Conversation location"><button type="button" onClick={()=>onBackToChat?.()} disabled={!onBackToChat}><ArrowLeft size={13} aria-hidden="true"/>Project coordination</button><ChevronRight size={12} aria-hidden="true"/><b aria-current="page">{selectedName}</b></nav>
      <div className="subchat-actions">
        <button className="small-button" disabled={!connected||conversationBusy} onClick={()=>void loadConversation(selected,true)}><RefreshCw size={14}/>{conversationBusy?'Reading…':'Refresh conversation'}</button>
        {onBackToChat&&<button className="small-button" onClick={onBackToChat}><MessageSquare size={14}/>Main conversation</button>}
        <button className="icon-btn" aria-label="Close focused conversation" onClick={()=>{setSelected('');setReceipt('');setChatError('');setChatReceipt('')}}><X size={16}/></button>
      </div>
    </header>
    <div className="subchat-history" role="log" aria-live="polite" aria-relevant="additions text" aria-label={`Native conversation with ${selectedName}`} ref={history} onScroll={e=>{const el=e.currentTarget;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<80}}>
      {conversationError&&<p role="alert" className="workers-error">{conversationError}</p>}
      {!conversationError&&conversation===null&&<p role="status" className="subchat-hint">Reading the native conversation…</p>}
      {!conversationError&&conversation!==null&&!conversationAvailable&&<p className="subchat-hint">{unavailableReason||'This provider does not expose worker conversation reading.'}</p>}
      {!conversationError&&conversationAvailable&&!conversationMessages.length&&<p className="subchat-hint">No native conversation recorded for {selectedName} yet. Replies to your direction appear here.</p>}
      {conversation?.truncated&&<p className="subchat-hint">Showing the most recent messages.</p>}{conversationAvailable&&conversationMessages.map((m,i)=><article key={m.messageId||m.id||`${i}-${m.role}-${m.text?.length||0}`} className={`subchat-message ${m.role==='user'?'user':'assistant'}`}>{m.role==='user'?m.text:<Markdown skipHtml components={markdown}>{m.text}</Markdown>}</article>)}
    </div>
    {(chatError||chatReceipt)&&<div className="subchat-status">{chatError&&<p role="alert" className="workers-error">{chatError}</p>}{chatReceipt&&<p role="status" className="workers-receipt">{chatReceipt}</p>}</div>}
    {canControl&&conversationAvailable&&<form className="worker-message" onSubmit={send}><label><MessageSquare size={15}/>Direction for {selectedName}<textarea aria-label="Message native worker" value={messageDrafts[selected]||''} onChange={e=>setMessageDrafts(old=>({...old,[selected]:e.target.value}))} placeholder="Add a constraint, clarify a task, or ask for an update…" maxLength={12000}/></label><button className="primary-button" disabled={!connected||busy||!(messageDrafts[selected]||'').trim()}><Send size={14}/>Send to worker</button></form>}
    {conversationAvailable&&<form className="worker-report" onSubmit={report}><label><CheckCircle2 size={15}/>Agree &amp; report to supervisor<textarea aria-label="Summary for the supervisor" value={reportDrafts[selected]||''} onChange={e=>setReportDrafts(old=>({...old,[selected]:e.target.value}))} placeholder="Write the decision you agree with. Nothing is sent until you choose Send report." maxLength={4000}/></label><button className="primary-button" disabled={!connected||busy||!(reportDrafts[selected]||'').trim()}><Send size={14}/>Send report</button><p className="worker-report-note">Your summary goes to the main supervisor conversation only when you send it. Opening or reading this conversation never reports.</p></form>}
  </div>}
  </section>
}
