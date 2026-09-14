# Verification

Verified locally on 2026-09-13 against the pinned Ruflo 3.41.2 / Claude Flow
CLI 3.33.0 installation. The test uses temporary project and state directories,
and `sandbox-exec` denies network and every write outside the temporary Ruflo
state root.

Run:

```text
/opt/homebrew/bin/python3 -B -m unittest -v /Users/uno/.local/share/agent-toolkit/ruflo-integration/test_integration.py
```

The tests prove:

- the exact advertised tool set matches `allowed-tools.json` and an
  `agent_spawn` call is rejected;
- a server launched from a non-project directory binds only through an explicit
  `project_root`, and rejects reuse for another project;
- task and exact decision memory survive server restart without product writes;
- two live server processes preserve concurrent task and memory writes;
- a lock older than 30 seconds is not evicted while its recorded owner PID is
  alive;
- no `.claude-flow` or `.swarm` directory appears in the synthetic project.

The general Ruflo CLI remains disabled. The pinned AgentDB bridge failed a
store/retrieve continuity check because it wrote and read different database
files; this facade uses Ruflo's `CLAUDE_FLOW_DISABLE_BRIDGE=1` single-database
path. Semantic search remains disabled because only the hash/mock embedding
fallback was available under the offline test.
