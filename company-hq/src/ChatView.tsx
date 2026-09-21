import React, {useEffect, useRef, useState} from 'react';
import Markdown from 'react-markdown';
import {ArrowDown, ArrowUpRight, Lightbulb, Code2, Telescope, Layers3} from 'lucide-react';
import './images.css';
type Data = Record<string, any>;
type Attachment = { id: string; name?: string; url: string };
type Message = {key:string;role:'user'|'assistant';text:string;complete:boolean;attachments?:Attachment[]};
function safeAttachmentUrl(value: unknown) { try { const url = new URL(String(value || ''), window.location.origin); return url.origin === window.location.origin && url.pathname.startsWith('/api/') ? url.href : ''; } catch { return ''; } }
export function conversationMessages(events:Data[]):Message[] {
  const messages:Message[]=[]; const items=new Map<string,Message>();
  for(const e of events) {
    if(e.type==='message.user') messages.push({key:`user-${e.seq}`,role:'user',text:e.data?.text||'',complete:true,attachments:Array.isArray(e.data?.attachments)?e.data.attachments.filter((item:Attachment)=>safeAttachmentUrl(item?.url)):[]});
    else if(e.type==='message.delta'||e.type==='message.completed') {
      const key=e.itemId||`turn-${e.turnId||e.seq}`; let message=items.get(key);
      if(!message){message={key,role:'assistant',text:'',complete:false};items.set(key,message);messages.push(message);}
      if(e.type==='message.completed'){message.text=e.data?.text||message.text;message.complete=true;}
      else if(!message.complete)message.text+=e.data?.text||'';
    }
  }
  return messages;
}
export default function ChatView({events,runtime,empty,composer,onDraft,busy,demo,onApproval}:{
  events:Data[];runtime:Data;empty:boolean;composer:React.ReactNode;onDraft:(text:string)=>void;
  busy:boolean;demo:boolean;onApproval:(id:string,decision:string)=>void;
}) {
  const scroll=useRef<HTMLDivElement>(null); const follow=useRef(true); const [atBottom,setAtBottom]=useState(true);
  const messages=conversationMessages(events); const working=busy||['starting','running','stopping'].includes(runtime.state);
  useEffect(()=>{if(follow.current&&scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight;},[events,working,runtime.pendingApprovals]);
  return <div className={`conversation ${empty&&!working?'welcome':'has-messages'}`}>
    {empty&&!working?<div className="welcome-scroll"><div className="welcome-inner">
      <div className="orb-scene" aria-hidden="true"><div className="orb-shadow"/><div className="orb-body"/><div className="orb-orbit"/><i className="orb-satellite"/></div>
      <div className="welcome-kicker">A LITTLE IDEA. A WORLD OF POSSIBILITIES.</div>
      <h1>What are we making today?</h1><p className="welcome-subtitle">An idea, a question, a next big thing.<br/>Just start talking. We’ll work it out together.</p>
      {composer}
      <div className="prompt-suggestions" aria-label="Conversation starters">
        {[[Lightbulb,'Shape an idea','Turn a spark into a plan','I have an idea for a product. Help me figure out who it is for and the smallest useful first version. Ask me what you need to know.'],[Code2,'Build something','From first step to finished','I want to build something new. Help me choose a useful starting point and make a small, testable plan.'],[Telescope,'Explore a question','Research, compare, understand','Help me research a question. Start by asking what I want to understand and what a useful answer would look like.']].map(([Icon,title,subtitle,prompt]:any)=><button key={title} onClick={()=>onDraft(prompt)}><div><Icon size={19}/><ArrowUpRight size={14}/></div><strong>{title}</strong><span>{subtitle}</span></button>)}
      </div><p className="welcome-footnote"><span/>Your pace. Your direction. A team when you need one.</p>
    </div></div>:<>
      <div className="conversation-scroll" ref={scroll} onScroll={()=>{const el=scroll.current;if(el){follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<100;setAtBottom(follow.current)}}}>
        <div className="message-list" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text">
          {demo&&<p className="fixture-notice">Synthetic demo · no provider calls</p>}
          {messages.map((message,index)=><article className={`chat-message ${message.role}`} key={message.key}>
            {message.role==='assistant'&&messages[index-1]?.role!=='assistant'&&<div className="message-byline"><span className="mini-mark"><Layers3 size={15}/></span>Supervisor<span>{runtime.model?.replace('gpt-','GPT ').replaceAll('-',' ') || 'Your team'}</span></div>}
            <div className="message-body">{message.role==='user'?<>{message.text}{message.attachments?.length ? <div className="message-attachments">{message.attachments.map(attachment => <img key={attachment.id} src={safeAttachmentUrl(attachment.url)} alt={attachment.name || 'Attached image'} />)}</div> : null}</>:<Markdown skipHtml components={{a:({children,...props})=><a {...props} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt})=><span>{alt?`[Image: ${alt}]`:'[Image]'}</span>}}>{message.text}</Markdown>}</div>
          </article>)}
          {working&&<div className="thinking-indicator" role="status"><span/><span/><span/>{busy?'Sending your message…':runtime.state==='starting'?'Connecting to Codex…':runtime.state==='stopping'?'Stopping…':'Working on it…'}</div>}
          {(runtime.pendingApprovals||[]).map((a:Data)=><section className="approval-card" key={a.requestId}><h3>Permission requested</h3><p>{a.reason}</p><pre>{a.command}</pre><div><button className="small-button" disabled={busy} onClick={()=>onApproval(a.requestId,'reject')}>Decline</button><button className="primary-button" disabled={busy} onClick={()=>onApproval(a.requestId,'approve')}>Approve once</button></div></section>)}
          {runtime.error&&<p className="chat-runtime-error" role="alert">{runtime.error}</p>}
          {!messages.length&&!working&&<p className="chat-recovery">This chat is ready to continue. Earlier messages may be unavailable after a server restart.</p>}
        </div>
      </div>
      {!atBottom&&<button className="jump-to-latest" aria-label="Jump to latest message" onClick={()=>{follow.current=true;scroll.current?.scrollTo({top:scroll.current.scrollHeight,behavior:'instant'});setAtBottom(true)}}><ArrowDown size={16}/></button>}
      <div className="conversation-compose">{composer}</div>
    </>}
  </div>;
}
