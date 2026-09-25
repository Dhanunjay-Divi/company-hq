import assert from 'node:assert/strict';
import {chatHierarchy, chatDescendants} from '../company-hq/src/chat-hierarchy.mjs';

const teams = ['lead', 'unrelated', 'head', 'worker'].map(name => ({name}));
const profiles = {
  head: {projectRoot:'/project'},
  lead: {projectRoot:'/project', supervisedBy:'head'},
  worker: {projectRoot:'/project', supervisedBy:'lead'},
  unrelated: {projectRoot:'/else', supervisedBy:'head'},
};
assert.deepEqual(chatHierarchy(teams, profiles).map(({team,depth})=>[team.name,depth]),
  [['unrelated',0],['head',0],['lead',1],['worker',2]]);
assert.deepEqual(chatHierarchy(teams, profiles, ['head']).map(({team,depth})=>[team.name,depth]),
  [['lead',0],['worker',1],['unrelated',0]]);
assert.deepEqual(chatDescendants(teams, profiles, 'head').map(team=>team.name), ['lead','worker']);
assert.deepEqual(chatDescendants(teams, profiles, 'head', ['lead']).map(team=>team.name), []);
console.log('chat hierarchy: verified');
