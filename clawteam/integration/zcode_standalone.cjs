// Company HQ compatibility adapter for the reviewed ZCode bundle (Apache-2.0).
// Reuses the installed runtime's standalone credential provider, also used by
// its own CLI. No credentials leave that provider. The installed app is unchanged.
const fs = require('node:fs');
const crypto = require('node:crypto');
const Module = require('node:module');
const path = require('node:path');
const entry = process.argv[2];
let source = fs.readFileSync(entry, 'utf8');
if (crypto.createHash('sha256').update(source).digest('hex') !== 'b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529') {
  throw new Error('ZCode changed. Review the native adapter before enabling this version.');
}
for (const [before, after] of [
 ['setExecutionState({mode:l},e.traceContext)', 'setExecutionState({mode:l==="plan"?"build":l,planEnabled:l==="plan"},e.traceContext)'],
 ['mode:{current:e.getMode()},model:{available:g', 'mode:{current:e.runtime.getPlanEnabled()?"plan":e.getMode()},model:{available:g'],
 ['create:r(()=>Ykt(z),"create")', 'create:r(()=>Ykt(z,{standalone:{...gPe(process.stderr)}}),"create")'],
 ['providerEndpointRoutingPort:ie,sourceTitle:"electron",onToolExecResource', 'providerRuntimeHeadersPort:rt.providerRuntimeHeadersPort,providerEndpointRoutingPort:ie,sourceTitle:"electron",onToolExecResource'],
]) {
 if (source.split(before).length !== 2) throw new Error('ZCode adapter target changed.');
 source = source.replace(before, after);
}
process.argv = [process.argv[0], entry, ...process.argv.slice(3)];
const native = new Module(entry, module);
native.filename = entry;
native.paths = Module._nodeModulePaths(path.dirname(entry));
native._compile(source, entry);
