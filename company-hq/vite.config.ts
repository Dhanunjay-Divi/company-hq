import {defineConfig} from 'vite';
import path from 'node:path';
export default defineConfig({esbuild:{jsx:'automatic'},resolve:{dedupe:['react','react-dom'],alias:{'d3-force':path.resolve('node_modules/d3-force/src/index.js'),'@claude-teams/agent-graph':path.resolve('vendor/agent-graph/src/index.ts')}},build:{target:'esnext',outDir:'dist',emptyOutDir:true}});
