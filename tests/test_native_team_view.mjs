import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeTeamView} from '../company-hq/src/native-team-view.mjs';
test('observed workers form actual parent chain without mutating recorded board',()=>{
 const board={team:{leaderName:'supervisor'},members:[{name:'supervisor'}],tasks:{pending:[]}};
 const company={members:{supervisor:{displayName:'Supervisor'}}};
 const result=nativeTeamView(board,company,{rootThreadId:'root',workers:[{threadId:'leaf',parentThreadId:'lead',role:'reviewer',model:'small'},{threadId:'lead',parentThreadId:'root',nickname:'Engineering',model:'balanced'}]});
 assert.equal(result.company.members['native-leaf'].reportsTo,'native-lead');
 assert.equal(result.company.members['native-lead'].reportsTo,'supervisor');
 assert.equal(result.company.members['native-lead'].displayName,'Engineering');
 assert.equal(board.members.length,1);assert.equal(Object.keys(company.members).length,1);
 assert.equal(result.snapshot.tasks,board.tasks);
});
test('duplicate observed worker is not duplicated; missing board remains absent',()=>{
 assert.deepEqual(nativeTeamView(null,{},{}),{snapshot:null,company:{}});
 const value=nativeTeamView({team:{leaderName:'boss'},members:[{name:'existing',agentId:'worker'}]}, {},{workers:[{threadId:'worker',model:'native'}]});
 assert.equal(value.snapshot.members.length,1);assert.equal(value.company.members.existing.model,'native');
 assert.equal(value.company.members.existing.reportsTo,null);
});
