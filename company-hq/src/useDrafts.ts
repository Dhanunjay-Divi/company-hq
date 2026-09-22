import {useEffect, useRef, useState} from 'react';
import {loadDraftStore, serializeDraftStore, DRAFT_STORAGE_KEY} from './draft-storage.mjs';
type Drafts=Record<string,string>;

/** Private server storage survives random loopback ports; browser storage is a
 * best-effort emergency copy, never the authoritative restart mechanism. */
export default function useDrafts(team:string,onError:(message:string)=>void){
  const [drafts,setDrafts]=useState<Drafts>(()=>Object.fromEntries(Object.entries(loadDraftStore()).map(([id,value]:any)=>[id==='new'?'':id,value.text])));
  const values=useRef(drafts);values.current=drafts;
  const revisions=useRef<Record<string,number>>({}),saved=useRef<Drafts>({}),inflight=useRef(new Set<string>());
  const [hydrated,setHydrated]=useState(0);
  useEffect(()=>{
    let active=true;let retry:ReturnType<typeof setTimeout>|undefined;const initial=values.current[team]||'';
    const hydrate=()=>fetch(`/api/drafts/${encodeURIComponent(team||'new')}`).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error);return d}).then(data=>{
      if(!active)return;revisions.current[team]=data.revision;saved.current[team]=data.text;
      if((values.current[team]||'')===initial&&(data.revision>0||!initial))setDrafts(old=>({...old,[team]:data.text}));
      setHydrated(v=>v+1);
    }).catch(()=>{if(active){onError('Draft recovery is unavailable. Retrying; keep this window open to preserve unsaved text.');retry=setTimeout(hydrate,5000);}});
    void hydrate();return()=>{active=false;if(retry)clearTimeout(retry)};
  },[team]);
  useEffect(()=>{
    try{localStorage.setItem(DRAFT_STORAGE_KEY,serializeDraftStore(Object.fromEntries(Object.entries(drafts).map(([id,text])=>[id||'new',{text,updatedAt:Date.now()}]))))}catch{}
    async function flush(){for(const [id,text] of Object.entries(values.current)){
      if(revisions.current[id]===undefined||saved.current[id]===text||inflight.current.has(id))continue;
      inflight.current.add(id);
      try{const r=await fetch(`/api/drafts/${encodeURIComponent(id||'new')}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,revision:revisions.current[id]}),keepalive:true});const data=await r.json();if(!r.ok)throw Error(data.error||'Draft could not be saved.');revisions.current[id]=data.revision;saved.current[id]=text;onError('')}
      catch(e:any){onError(e.message||'Draft could not be saved.');}
      finally{inflight.current.delete(id);if(saved.current[id]===text&&values.current[id]!==text)setHydrated(v=>v+1)}
    }}
    const timer=setTimeout(flush,350);const retry=setInterval(flush,5000);const leaving=()=>{void flush()};window.addEventListener('pagehide',leaving);
    return()=>{clearTimeout(timer);clearInterval(retry);window.removeEventListener('pagehide',leaving)};
  },[drafts,hydrated]);
  return [drafts,setDrafts] as const;
}
