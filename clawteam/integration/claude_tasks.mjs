// Official SDK metadata APIs only. No query(), prompts, transcript body or auth reads.
import {pathToFileURL} from 'node:url';
const [sdkPath, requestText]=process.argv.slice(2);
const request=JSON.parse(requestText);
const sdk=await import(pathToFileURL(sdkPath).href);
function project(row){return {id:row.sessionId,title:String(row.customTitle||row.summary||'Untitled Claude task').slice(0,180),summary:String(row.summary||'').slice(0,2000),project:row.cwd||null,updatedAt:row.lastModified,status:'Not reported',source:'Claude Code SDK'}}
if(request.action==='list'){
  const rows=await sdk.listSessions({limit:31,offset:request.offset,includeProgrammatic:request.includeAgents});
  const tasks=rows.slice(0,30).map(project);
  console.log(JSON.stringify({provider:'claude',readOnly:true,tasks:tasks.filter(row=>!request.search||(row.title+' '+row.summary).toLowerCase().includes(request.search.toLowerCase())),nextCursor:rows.length>30?String(request.offset+30):null,searchScope:'current page'}));
}else if(request.action==='read'){
  const row=await sdk.getSessionInfo(request.id);
  if(!row)throw Error('Task metadata unavailable');
  console.log(JSON.stringify({provider:'claude',readOnly:true,task:project(row)}));
}else throw Error('Unsupported metadata action');
