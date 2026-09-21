"""Exercise real frontend retention with long streams and overlapping polls."""
from pathlib import Path
import subprocess
import unittest


class EventFeedTests(unittest.TestCase):
    def test_long_stream_keeps_question_and_final_answer(self):
        module = (Path(__file__).resolve().parents[1] / 'company-hq/src/event-feed.mjs').as_uri()
        script = '''
import assert from 'node:assert/strict';
import {mergeRuntimeEvents} from MODULE;
const event=(seq,type,text)=>({seq,type,itemId:type==='message.user'?'question':'reply',threadId:'fixture',data:{text}});
let feed=[event(1,'message.user','What should we build?')];
for(let start=2;start<602;start+=20) {
  const page=Array.from({length:20},(_,i)=>event(start+i,'message.delta','x'));
  feed=mergeRuntimeEvents(feed,page);
  feed=mergeRuntimeEvents(feed,page); // A retried poll must not duplicate text.
}
assert.equal(feed.filter(e=>e.type==='message.user').length,1);
assert.equal(feed.find(e=>e.type==='message.delta').data.text,'x'.repeat(600));
feed=mergeRuntimeEvents(feed,[event(602,'message.completed','Build the smallest useful version.')]);
assert.equal(feed.filter(e=>e.type==='message.delta').length,0);
assert.equal(feed.find(e=>e.type==='message.user').data.text,'What should we build?');
assert.equal(feed.find(e=>e.type==='message.completed').data.text,'Build the smallest useful version.');
assert.equal(mergeRuntimeEvents(feed,[event(601,'message.delta','stale')]).length,2);
assert.equal(mergeRuntimeEvents([],Array.from({length:700},(_,i)=>event(i+1,'status','bounded'))).length,500);
'''.replace('MODULE', repr(module))
        subprocess.run(['node', '--input-type=module', '-e', script], check=True, timeout=15)
