# Agent graph upstream

`agent-graph/` is a copy of `packages/agent-graph` from Agent Teams
AI at commit `c2e9212e7a1a8daed34d7464432fc18eec62b238` (release line
`v2.14.2`). The package is reused through its public port interfaces by
`src/TeamGraph.tsx`.

Local change (2026-09-13): `src/hooks/useGraphCamera.ts` caps automatic fit zoom
at 1, preventing a single teammate from being enlarged beyond the viewport.
Manual zoom remains available. All other upstream source is retained.

Agent Teams AI is copyright © 2026 Илия (777genius) and licensed under the GNU
Affero General Public License version 3. The complete license is retained as
`AGENT-TEAMS-AI-AGPL-3.0.txt`. A host UI using this component must present the
AGPL copyright, warranty, source, and license notice required for an interactive
interface.

Runtime dependencies required by the package are React, React DOM, d3-force,
lucide-react, and `@floating-ui/dom`. The last dependency is imported by
`GraphView` even though upstream's leaf `package.json` currently omits it.
