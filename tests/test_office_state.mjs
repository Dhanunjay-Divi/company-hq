import test from 'node:test';
import assert from 'node:assert/strict';
import {officeState,exampleOffice} from '../company-hq/src/office-state.mjs';
const board={team:{leaderName:'head'},members:[{name:'head'},{name:'recorded',agentId:'recorded-id'}],tasks:{in_progress:[{id:'t',subject:'Recorded task',owner:'recorded'}]}};
test('recorded assignments do not create working animations or fake models',()=>{
 const s=officeState(board);assert.equal(s.agents[1].status,'recorded');assert.equal(s.agents[1].model,'');assert.equal(s.agents[1].task.title,'Recorded task');assert.deepEqual(s.messages,[]);assert.deepEqual(officeState(null),{agents:[],messages:[]});
});
test('observed hierarchy and stale state survive presentation without mutating the board',()=>{
 const roster={connected:true,rootThreadId:'root',workers:[{threadId:'lead',parentThreadId:'root',status:'active',model:'small',nickname:'Lead'},{threadId:'worker',parentThreadId:'lead',status:'active',stale:true}]};
 const s=officeState(board,{},roster,{threadId:'root',connected:true,state:'running'});
 assert.equal(s.agents[0].status,'working');assert.equal(s.agents[2].status,'working');assert.equal(s.agents[2].reportsTo,'head');assert.equal(s.agents[3].reportsTo,'native-lead');assert.equal(s.agents[3].status,'offline');assert.equal(board.members.length,2);
 assert.equal(officeState(board,{},roster,{connected:false}).agents[2].status,'offline');
});
test('send receipts are deduplicated and never called delivered',()=>{
 const e={seq:4,type:'worker.message_sent',time:1,data:{workerThreadId:'worker'}};
 const s=officeState(board,{}, {workers:[{threadId:'worker'}]}, {},[e,e,{...e,seq:5,data:{workerThreadId:'foreign'}}]);
 assert.equal(s.messages.length,1);assert.equal(s.messages[0].state,'accepted');assert.equal(s.messages[0].from,'You');assert.equal(s.messages[0].to,'native-worker');
});
test('example fixture is explicit and never pretends to be observed',()=>{
 assert.equal(exampleOffice().agents.length,6);assert.ok(exampleOffice().agents.every(a=>!a.observed));assert.deepEqual(exampleOffice().messages,[]);
});
test('a delegated provider session is not labeled the overall supervisor',()=>{
 const s=officeState(board,{executionRole:'worker',supervisedBy:'Outer Codex reviewer'}, {},{threadId:'glm',connected:true,model:'GLM-5.3'});
 assert.equal(s.agents[0].role,'Delegated builder');assert.equal(s.agents[0].reportsTo,'Outer Codex reviewer');assert.equal(s.agents[0].delegated,true);
 assert.equal(officeState(board,{}, {},{threadId:'root'}).agents[0].role,'Overall supervisor');
});
