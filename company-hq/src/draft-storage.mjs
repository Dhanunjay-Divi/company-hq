/**
 * Browser-only, per-chat composer drafts.  This module intentionally stores
 * text only: attachments, credentials, and runtime data never belong here.
 */
export const DRAFT_STORAGE_KEY = 'company-hq.chat-drafts.v1';
export const DRAFT_SCHEMA_VERSION = 1;
export const MAX_DRAFT_CHARS = 24_000;
export const MAX_DRAFT_CHATS = 50;
export const MAX_DRAFT_BYTES = 512 * 1024;

function byteLength(value) {
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(value).length;
  return unescape(encodeURIComponent(value)).length;
}

function storageFor(storage) {
  if (storage) return storage;
  try { return globalThis.localStorage; } catch { return null; }
}

function cleanChatId(chatId) {
  return typeof chatId === 'string' && chatId.length > 0 && chatId.length <= 200 ? chatId : '';
}

function cleanText(text) {
  return typeof text === 'string' ? text.slice(0, MAX_DRAFT_CHARS) : '';
}

/** Convert untrusted browser storage into a small, current-schema record. */
export function parseDraftStore(raw) {
  if (typeof raw !== 'string' || raw.length > MAX_DRAFT_BYTES) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== DRAFT_SCHEMA_VERSION || !parsed.drafts || typeof parsed.drafts !== 'object' || Array.isArray(parsed.drafts)) return {};
    const entries = Object.entries(parsed.drafts)
      .filter(([chatId, value]) => cleanChatId(chatId) && value && typeof value === 'object' && typeof value.text === 'string')
      .map(([chatId, value]) => [chatId, { text: cleanText(value.text), updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : 0 }])
      .filter(([, value]) => value.text);
    entries.sort((a, b) => b[1].updatedAt - a[1].updatedAt);
    return Object.fromEntries(entries.slice(0, MAX_DRAFT_CHATS));
  } catch { return {}; }
}

export function serializeDraftStore(drafts) {
  const entries = Object.entries(drafts || {})
    .filter(([chatId, value]) => cleanChatId(chatId) && value && typeof value.text === 'string' && cleanText(value.text))
    .map(([chatId, value]) => [chatId, { text: cleanText(value.text), updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : 0 }])
    .sort((a, b) => b[1].updatedAt - a[1].updatedAt);
  const kept = {};
  for (const [chatId, value] of entries.slice(0, MAX_DRAFT_CHATS)) {
    const candidate = JSON.stringify({ version: DRAFT_SCHEMA_VERSION, drafts: { ...kept, [chatId]: value } });
    if (byteLength(candidate) > MAX_DRAFT_BYTES) continue;
    kept[chatId] = value;
  }
  return JSON.stringify({ version: DRAFT_SCHEMA_VERSION, drafts: kept });
}

export function loadDraftStore(storage) {
  const target = storageFor(storage);
  if (!target) return {};
  try { return parseDraftStore(target.getItem(DRAFT_STORAGE_KEY)); } catch { return {}; }
}

export function loadChatDraft(chatId, storage) {
  const id = cleanChatId(chatId);
  return id ? loadDraftStore(storage)[id]?.text || '' : '';
}

/** Save an individual draft. Empty text removes it. Returns false if storage is denied. */
export function saveChatDraft(chatId, text, storage, now = Date.now()) {
  const target = storageFor(storage), id = cleanChatId(chatId);
  if (!target || !id) return false;
  const drafts = loadDraftStore(target);
  const cleaned = cleanText(text);
  if (cleaned) drafts[id] = { text: cleaned, updatedAt: Number.isFinite(now) ? now : Date.now() };
  else delete drafts[id];
  try { target.setItem(DRAFT_STORAGE_KEY, serializeDraftStore(drafts)); return true; } catch { return false; }
}

export function removeChatDraft(chatId, storage) {
  return saveChatDraft(chatId, '', storage);
}
