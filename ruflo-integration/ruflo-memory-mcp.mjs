#!/usr/bin/env node
/**
 * Project-scoped Ruflo task/decision-memory MCP facade.
 * Native Codex executes workers; this process only maintains local metadata.
 */
import { createHash, randomUUID } from 'node:crypto';
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homedir } from 'node:os';

const INTEGRATION_DIR = dirname(fileURLToPath(import.meta.url));
const TOOLKIT_DIR = realpathSync(resolve(INTEGRATION_DIR, '..'));
const RUFLO_DIR = realpathSync(join(TOOLKIT_DIR, 'ruflo-3.41.2'));
const CLI_DIR = join(RUFLO_DIR, 'node_modules', '@claude-flow', 'cli');
const CONFIG_PATH = join(INTEGRATION_DIR, 'allowed-tools.json');
const MAX_LINE_BYTES = 2 * 1024 * 1024;
const LOCK_WAIT_MS = 5_000;
const LOCK_STALE_MS = 30_000;

function fail(message) {
  process.stderr.write(`ruflo-memory-mcp: ${message}\n`);
  process.exit(1);
}

function requireDirectory(path, label) {
  let physical;
  try {
    physical = realpathSync(path);
  } catch {
    throw new Error(`${label} must be an existing directory: ${path}`);
  }
  if (!statSync(physical).isDirectory()) throw new Error(`${label} is not a directory: ${physical}`);
  return physical;
}

const stateBase = process.env.XDG_STATE_HOME
  ? resolve(process.env.XDG_STATE_HOME)
  : join(homedir(), '.local', 'state');
let stateRoot = resolve(process.env.RUFLO_INTEGRATION_STATE_ROOT || join(stateBase, 'company-hq', 'ruflo'));
const stateRelativeToSource = relative(TOOLKIT_DIR, stateRoot);
if (
  stateRoot === resolve('/') ||
  stateRoot === realpathSync(homedir()) ||
  stateRoot === TOOLKIT_DIR ||
  (!stateRelativeToSource.startsWith('..') && !isAbsolute(stateRelativeToSource))
) {
  fail('state root must be an external private directory, not source checkout or account home');
}
mkdirSync(stateRoot, { recursive: true, mode: 0o700 });
let projectRoot;
let scopeID;
let scopeDir;
let runtimeDir;
let memoryDir;

const configured = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
if (configured.schema !== 1 || !Array.isArray(configured.tools)) fail('invalid allowed-tools.json');
const allowedNames = new Set(configured.tools);
if (allowedNames.size !== configured.tools.length) fail('duplicate tool in allowed-tools.json');

process.env.CLAUDE_FLOW_AUTO_UPDATE = 'false';
// Pinned 3.41.2's optional AgentDB bridge writes a sibling database that its
// public memory_retrieve path does not read in this install. Use Ruflo's own
// coherent sql.js memory.db path until that upstream split-store bug is fixed.
process.env.CLAUDE_FLOW_DISABLE_BRIDGE = '1';
process.env.HF_HUB_OFFLINE = '1';
process.env.TRANSFORMERS_OFFLINE = '1';

// Block JavaScript fetch even if an embedding dependency ignores offline flags.
globalThis.fetch = async () => { throw new Error('network disabled by ruflo-memory-mcp'); };
// Ruflo dependencies sometimes log model/backend diagnostics with console.log.
// Keep stdout exclusively newline-delimited MCP JSON-RPC.
console.log = (...items) => process.stderr.write(`${items.map(String).join(' ')}\n`);

const modules = await Promise.all([
  import(pathToFileURL(join(CLI_DIR, 'dist/src/mcp-tools/memory-tools.js'))),
  import(pathToFileURL(join(CLI_DIR, 'dist/src/mcp-tools/task-tools.js'))),
  import(pathToFileURL(join(CLI_DIR, 'dist/src/mcp-tools/coordination-tools.js'))),
]);
const available = [...modules[0].memoryTools, ...modules[1].taskTools, ...modules[2].coordinationTools];
const registry = new Map(available.filter((tool) => allowedNames.has(tool.name)).map((tool) => [tool.name, tool]));
for (const name of allowedNames) {
  if (!registry.has(name)) fail(`configured tool is unavailable in pinned Ruflo: ${name}`);
}

function response(id, result) { return { jsonrpc: '2.0', id, result }; }
function error(id, code, message) { return { jsonrpc: '2.0', id, error: { code, message } }; }
function emit(message) { process.stdout.write(`${JSON.stringify(message)}\n`); }
function sleep(ms) { return new Promise((done) => setTimeout(done, ms)); }

function bindProject(input) {
  const requested = input?.project_root || process.env.RUFLO_PROJECT_ROOT;
  if (typeof requested !== 'string' || !requested) {
    throw new Error('project_root is required (or set RUFLO_PROJECT_ROOT for a per-project launch)');
  }
  if (!isAbsolute(requested)) throw new Error('project_root must be absolute');
  const physical = requireDirectory(requested, 'project root');
  if (physical === '/' || physical === realpathSync(homedir())) {
    throw new Error('refusing a filesystem root or home directory as a project scope');
  }
  if (projectRoot && physical !== projectRoot) {
    throw new Error(`server is already bound to a different project; start a separate MCP process for ${physical}`);
  }
  if (!projectRoot) {
    projectRoot = physical;
    scopeID = createHash('sha256').update(projectRoot).digest('hex');
    scopeDir = join(stateRoot, 'projects', scopeID);
    runtimeDir = join(scopeDir, 'runtime');
    memoryDir = join(scopeDir, 'memory');
    mkdirSync(runtimeDir, { recursive: true, mode: 0o700 });
    mkdirSync(memoryDir, { recursive: true, mode: 0o700 });
    const scopePath = join(scopeDir, 'scope.json');
    const document = `${JSON.stringify({ schema: 1, project: projectRoot, scope_id: scopeID }, null, 2)}\n`;
    if (existsSync(scopePath)) {
      const existing = JSON.parse(readFileSync(scopePath, 'utf8'));
      if (existing.schema !== 1 || existing.project !== projectRoot || existing.scope_id !== scopeID) {
        throw new Error('project scope identity mismatch');
      }
    } else {
      const temporary = `${scopePath}.${process.pid}.${randomUUID()}.tmp`;
      writeFileSync(temporary, document, { mode: 0o600, flag: 'wx' });
      try {
        renameSync(temporary, scopePath);
      } catch (cause) {
        rmSync(temporary, { force: true });
        if (!existsSync(scopePath)) throw cause;
      }
    }
    // All Ruflo relative state paths resolve under this external project scope.
    process.chdir(runtimeDir);
    process.env.CLAUDE_FLOW_CWD = runtimeDir;
    process.env.CLAUDE_FLOW_MEMORY_PATH = memoryDir;
    process.env.CLAUDE_FLOW_DB_PATH = join(memoryDir, 'memory.db');
    process.stderr.write(`ruflo-memory-mcp: bound project scope ${scopeID.slice(0, 12)}\n`);
  }
  const args = { ...(input || {}) };
  delete args.project_root;
  return args;
}

function ownerIsAlive(lockDir) {
  try {
    const owner = JSON.parse(readFileSync(join(lockDir, 'owner.json'), 'utf8'));
    if (!Number.isSafeInteger(owner.pid) || owner.pid <= 0) return false;
    try {
      process.kill(owner.pid, 0);
      return true;
    } catch (cause) {
      return cause?.code === 'EPERM';
    }
  } catch {
    return false;
  }
}

async function acquireWriteLock() {
  const lockDir = join(scopeDir, '.write.lock');
  const started = Date.now();
  const token = randomUUID();
  while (Date.now() - started < LOCK_WAIT_MS) {
    try {
      mkdirSync(lockDir, { mode: 0o700 });
      const owner = join(lockDir, 'owner.json');
      writeFileSync(owner, JSON.stringify({ pid: process.pid, time: Date.now(), token }), { mode: 0o600, flag: 'wx' });
      return () => {
        try {
          const current = JSON.parse(readFileSync(owner, 'utf8'));
          if (current.token === token) rmSync(lockDir, { recursive: true, force: true });
        } catch { /* already released or replaced */ }
      };
    } catch {
      try {
        if (Date.now() - statSync(lockDir).mtimeMs > LOCK_STALE_MS && !ownerIsAlive(lockDir)) {
          rmSync(lockDir, { recursive: true, force: true });
          continue;
        }
      } catch { /* another process changed the lock */ }
      await sleep(20);
    }
  }
  throw new Error('project memory write lock timed out');
}

let requestQueue = Promise.resolve();
async function callTool(name, args) {
  const tool = registry.get(name);
  if (!tool) throw new Error(`tool not allowed: ${String(name)}`);
  const toolArgs = bindProject(args);
  const release = await acquireWriteLock();
  try {
    return await tool.handler(toolArgs, { projectRoot });
  } finally {
    release();
  }
}

async function handle(message) {
  if (!message || message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
    return error(message?.id ?? null, -32600, 'Invalid Request');
  }
  if (message.method === 'initialize') {
    return response(message.id, {
      protocolVersion: '2024-11-05',
      serverInfo: { name: 'ruflo-project-memory', version: '1.0.0', ruflo: '3.41.2' },
      capabilities: { tools: { listChanged: false } },
    });
  }
  if (message.method === 'notifications/initialized') return null;
  if (message.method === 'ping') return response(message.id, {});
  if (message.method === 'tools/list') {
    return response(message.id, { tools: [...registry.values()].map(({ name, description, inputSchema }) => ({
      name,
      description: `${name === 'memory_store' ? 'Persist an exact key/value decision or finding; semantic search is not enabled.' : description.split(' Use when native ')[0]} Uses external project state; pass project_root.`,
      inputSchema: {
        ...inputSchema,
        properties: {
          ...(inputSchema?.properties || {}),
          project_root: { type: 'string', description: 'Absolute project directory used only to select isolated external Ruflo state' },
        },
      },
    })) });
  }
  if (message.method === 'tools/call') {
    const name = message.params?.name;
    if (!registry.has(name)) return error(message.id, -32601, `Tool not allowed: ${String(name)}`);
    try {
      const result = await callTool(name, message.params?.arguments || {});
      return response(message.id, { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] });
    } catch (cause) {
      return error(message.id, -32603, cause instanceof Error ? cause.message : 'Tool execution failed');
    }
  }
  return error(message.id, -32601, `Method not found: ${message.method}`);
}

let inputBuffer = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  inputBuffer += chunk;
  if (Buffer.byteLength(inputBuffer, 'utf8') > MAX_LINE_BYTES) {
    emit(error(null, -32700, 'Buffered input exceeds limit'));
    inputBuffer = '';
    return;
  }
  const lines = inputBuffer.split('\n');
  inputBuffer = lines.pop() || '';
  for (const line of lines) {
    if (!line.trim()) continue;
    requestQueue = requestQueue.then(async () => {
      let message;
      try { message = JSON.parse(line); } catch { emit(error(null, -32700, 'Parse error')); return; }
      const result = await handle(message);
      if (result) emit(result);
    }).catch((cause) => emit(error(null, -32603, cause instanceof Error ? cause.message : 'Internal error')));
  }
});
process.stdin.on('end', async () => { await requestQueue; });

process.stderr.write(`ruflo-memory-mcp: pinned Ruflo 3.41.2; awaiting project_root; ${registry.size} metadata tools\n`);
