/** Join verified native hierarchy with recorded board metadata, without writing
 * registrations or guessing task ownership. */
export function nativeTeamView(snapshot,company,roster){
  if(!snapshot)return {snapshot,company};
  const members=[...(snapshot.members||[])],profiles={...(company.members||{})};
  const ids=new Map(members.filter(m=>m.agentId).map(m=>[m.agentId,m.name]));
  if(roster.rootThreadId)ids.set(roster.rootThreadId,snapshot.team.leaderName);
  const workers=roster.workers||[];
  for(const worker of workers){
    if(!worker.threadId||ids.has(worker.threadId))continue;
    const name=`native-${worker.threadId}`;ids.set(worker.threadId,name);
    members.push({name,agentId:worker.threadId,agentType:worker.role||'native-worker'});
  }
  for(const worker of workers){
    const name=ids.get(worker.threadId);if(!name)continue;
    profiles[name]={...profiles[name],displayName:worker.nickname||worker.role||'Native worker',
      department:worker.role||'Specialist',model:worker.model||'',reportsTo:ids.get(worker.parentThreadId)||null};
  }
  return {snapshot:{...snapshot,members},company:{...company,members:profiles}};
}
