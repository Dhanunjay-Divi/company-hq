# Company dashboard design — 2026-09-13

User reference: Agent Teams AI graph screenshot and
https://github.com/777genius/agent-teams-ai.

Reviewed upstream source at c2e9212e7a1a8daed34d7464432fc18eec62b238:
- features/agent-graph/renderer/adapters/TeamGraphAdapter.ts: stable lead/member
  identities, per-owner task and activity projection, evidence-based runtime
  states and real message events.
- features/organizations/core/domain/organizationGraph.ts: organization and
  nested unit/team hierarchy, cycle handling and team activity projection.

Use those interaction concepts in the existing ClawTeam dashboard: a readable
lead-to-supervisor-to-specialist map, inspectable owner cards, task and activity
views, direct recipient selection, simple onboarding and clear connection state.
The integration uses ClawTeam's task and inbox stores; it does not claim Agent
Teams AI runtime, analytics, deployment or full organization-editor parity.

Company profiles describe actual assignments. They do not manufacture working
agents or teams, and model labels do not measure tokens or subscription access.
User messages are attributed to user. Saving a task does not execute it; inbox
messages are read at native agent checkpoints. Immediate steering and new
project execution start in the supervising Codex conversation.
