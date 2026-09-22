import React, {useState} from 'react';
import './plan-panel.css';
type Step={key:string;title:string;description:string;owner:string;dependsOn:string[];acceptance:string};
type Plan={goal:string;steps:Step[];taskIDs?:Record<string,string>;statuses?:Record<string,string>};
type Props={team:string;currenttasks:any[];currentmembers:string[];onDraft:(text:string)=>void};
export default function PlanPanel({team,currenttasks,currentmembers,onDraft}:Props){
  const [text,setText]=useState(''),[requestId,setRequestId]=useState(''),[applied,setApplied]=useState(false);
  const [plan,setPlan]=useState<Plan|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function call(action:string,body:object){
    const response=await fetch(`/api/plans/${encodeURIComponent(team)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const value=await response.json();if(!response.ok)throw Error(value.error||'The plan could not be saved.');return value;
  }
  async function preview(){setBusy(true);setError('');try{setPlan(await call('preview',{plan:JSON.parse(text)}));setRequestId(crypto.randomUUID());setApplied(false)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function apply(){if(!plan)return;setBusy(true);setError('');try{setPlan(await call('apply',{plan:{goal:plan.goal,steps:plan.steps},requestId}));setApplied(true)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  return <section className="plan-panel"><h2>From idea to delivery</h2><p>Ask for a plan with owners and clear checks. The supervisor can add it directly to this board.</p>
    <button className="small-button" onClick={()=>onDraft(`Plan the work for our goal. Use the HQ plan tool to record concrete deliverables, dependencies, owners and acceptance checks. Registered owners: ${currentmembers.join(', ')}. Then follow this chat's access mode to execute and verify the work.`)}>Plan with the supervisor</button>
    {plan&&<div className="plan-card"><b>{plan.goal}</b>{plan.steps.map(step=>{
      const actual=currenttasks.find(task=>task.id===plan.taskIDs?.[step.key]);
      return <article key={step.key}><strong>{step.title}</strong><span>{step.owner}{applied?` · ${actual?.status||plan.statuses?.[step.key]||'Status unavailable'}`:''}</span><p>{step.description}</p><small>Depends on: {step.dependsOn.join(', ')||'None'} · Check: {step.acceptance}</small></article>
    })}<button className="primary-button" disabled={busy||applied} onClick={apply}>{applied?'Added to the board':busy?'Saving…':'Add tasks to board'}</button></div>}
    <details><summary>Import a structured plan</summary><p>Adding a plan records tasks. It does not start agents.</p><textarea aria-label="Plan JSON" value={text} onChange={e=>{setText(e.target.value);setPlan(null);setRequestId('');setApplied(false)}} placeholder='{"goal":"…","steps":[]}'/><button className="small-button" disabled={busy||!text.trim()} onClick={preview}>Preview plan</button></details>
    {error&&<p role="alert">{error}</p>}
  </section>
}
