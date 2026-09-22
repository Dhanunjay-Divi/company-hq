import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DRAFT_STORAGE_KEY, DRAFT_SCHEMA_VERSION, MAX_DRAFT_CHARS,
  loadChatDraft, loadDraftStore, parseDraftStore, removeChatDraft, saveChatDraft,
} from '../company-hq/src/draft-storage.mjs';

function fakeStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return { getItem: key => values.has(key) ? values.get(key) : null, setItem: (key, value) => values.set(key, value), values };
}

test('saves, loads, and removes a draft by chat id', () => {
  const storage = fakeStorage();
  assert.equal(saveChatDraft('chat-a', 'Keep this after restart.', storage, 10), true);
  assert.equal(loadChatDraft('chat-a', storage), 'Keep this after restart.');
  assert.equal(removeChatDraft('chat-a', storage), true);
  assert.equal(loadChatDraft('chat-a', storage), '');
});

test('ignores corrupt, unknown-version, and oversized stored values', () => {
  assert.deepEqual(parseDraftStore('{broken'), {});
  assert.deepEqual(parseDraftStore(JSON.stringify({ version: 99, drafts: { chat: { text: 'nope' } } })), {});
  assert.deepEqual(parseDraftStore('x'.repeat(600 * 1024)), {});
});

test('bounds text and omits malformed draft entries', () => {
  const storage = fakeStorage();
  saveChatDraft('chat-a', 'x'.repeat(MAX_DRAFT_CHARS + 50), storage, 1);
  assert.equal(loadChatDraft('chat-a', storage).length, MAX_DRAFT_CHARS);
  storage.values.set(DRAFT_STORAGE_KEY, JSON.stringify({ version: DRAFT_SCHEMA_VERSION, drafts: { good: { text: 'yes', updatedAt: 1 }, bad: { text: 7 } } }));
  assert.deepEqual(loadDraftStore(storage), { good: { text: 'yes', updatedAt: 1 } });
});

test('fails closed when browser storage denies reads or writes', () => {
  const denied = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.deepEqual(loadDraftStore(denied), {});
  assert.equal(saveChatDraft('chat-a', 'draft', denied), false);
});
