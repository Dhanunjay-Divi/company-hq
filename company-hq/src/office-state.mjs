import {nativeTeamView} from './native-team-view.mjs';

/** Presentation only. Task state never proves native liveness or delivery. */
export function officeState(snapshot, company={}, roster={}, runtime={}, events=[]) {
  if (!snapshot) return {agents:[], messages:[]};
  const joined=nativeTeamView(snapshot,company,roster);
  const leader=snapshot.team?.leaderName;
  const tasks=Object.entries(snapshot.tasks||{}).flatMap(([status,items])=>items.map(t=>({...t,status})));
  const workers=new Map((roster.workers||[]).map(w=>[w.threadId,w]));
  const ids=new Map(joined.snapshot.members.filter(m=>m.agentId).map(m=>[m.agentId,m.name]));
  if(runtime.threadId) ids.set(runtime.threadId,leader);
  const agents=joined.snapshot.members.map(m=>{
    const p=joined.company.members?.[m.name]||{}, supervisor=m.name===leader, w=workers.get(m.agentId);
    const observed=supervisor?!!runtime.threadId:!!w;
    const stale=supervisor?!runtime.connected:!runtime.connected||!roster.connected||!!w?.stale;
    const raw=supervisor?runtime.state:w?.status;
    const status=!observed?'recorded':stale?'offline':raw==='running'||raw==='active'?'working':raw==='awaiting_approval'?'waiting':raw==='idle'?'idle':raw==='error'||raw==='systemError'?'error':'unknown';
    const labels={recorded:'Recorded role',offline:'Needs refresh',working:'Working',waiting:'Needs your input',idle:'Ready',error:'Needs attention',unknown:'Status not reported'};
    const assigned=tasks.filter(t=>t.owner===m.name||t.owner===m.agentId);
    const task=assigned.find(t=>t.status==='in_progress')||assigned.find(t=>t.status==='blocked')||assigned.find(t=>t.status==='pending');
    const delegated=supervisor&&['worker','lead'].includes(company.executionRole);
    return {id:m.name,name:p.displayName||m.name,role:supervisor?(delegated?company.executionRole==='lead'?'Delegated lead':'Delegated builder':'Overall supervisor'):w?.role||p.department||m.agentType||'Specialist',model:supervisor?runtime.model||p.model||'':w?.model||p.model||'',isSupervisor:supervisor,delegated,observed,stale,status,statusLabel:labels[status],reportsTo:delegated?company.supervisedBy:p.reportsTo||undefined,...(task?{task:{id:task.id,title:task.subject,status:task.status}}:{})};
  });
  // Only explicit send receipts: no invented lead-to-worker conversation.
  const messages=[...new Map(events.filter(e=>e.type==='worker.message_sent'&&ids.has(e.data?.workerThreadId)).map(e=>[e.seq,{id:String(e.seq),from:'You',to:ids.get(e.data.workerThreadId),text:'Direction submitted to the native worker. Receipt is not confirmation it was read.',createdAt:new Date(e.time).toISOString(),state:'accepted'}])).values()].slice(-5);
  return {agents,messages};
}

export function exampleOffice() {
  return {agents:[
    ['head','Supervisor','Direction & review','working',null],
    ['lead','Engineering lead','Engineering','working','head'],
    ['research','Researcher','Customer research','idle','head'],
    ['design','Designer','Product design','working','head'],
    ['build','Builder','Implementation','working','lead'],
    ['review','Reviewer','Quality','waiting','lead'],
  ].map(([id,name,role,status,reportsTo])=>({id,name,role,status,reportsTo,model:'Illustrative role',statusLabel:status==='working'?'Example: working':status==='idle'?'Example: ready':'Example: waiting',isSupervisor:id==='head',observed:false,stale:false,task:{id:'example-'+id,title:{head:'Review the first milestone',lead:'Coordinate the build',research:'Summarize customer interviews',design:'Design the first experience',build:'Build the agreed feature',review:'Check behavior and accessibility'}[id],status:'pending'}})),messages:[]};
}
