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

const recentlyActive = [
  {name:'old-project',lastActivityAt:10},
  {name:'new-project',lastActivityAt:40},
  {name:'old-project-worker',lastActivityAt:90},
  {name:'new-project-worker',lastActivityAt:50},
  {name:'old-project-lead',lastActivityAt:60},
];
const recentProfiles = {
  'old-project': {projectRoot:'/old'},
  'old-project-lead': {projectRoot:'/old',supervisedBy:'old-project'},
  'old-project-worker': {projectRoot:'/old',supervisedBy:'old-project-lead'},
  'new-project': {projectRoot:'/new'},
  'new-project-worker': {projectRoot:'/new',supervisedBy:'new-project'},
};
assert.deepEqual(chatHierarchy(recentlyActive,recentProfiles).map(({team,depth})=>[team.name,depth]), [
  ['old-project',0], ['old-project-lead',1], ['old-project-worker',2],
  ['new-project',0], ['new-project-worker',1],
]);
assert.deepEqual(chatHierarchy([...recentlyActive,{name:'standalone',lastActivityAt:100}],recentProfiles)
  .map(({team})=>team.name)[0], 'standalone');
console.log('chat hierarchy: verified');
