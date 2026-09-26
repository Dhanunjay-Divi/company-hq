# Company HQ

A local AI engineering workspace for taking an idea through planning, implementation, review and launch. Company HQ is the control plane; provider runtimes, task/memory/code-intelligence systems and specialist skills sit behind explicit adapters rather than competing for authority.

Company HQ is a local development application for macOS Apple Silicon. Open **Company HQ.app**, start chatting, and attach a project only when you want to work with its files. The application keeps private state outside the checkout and uses the provider accounts you connect. See the [release acceptance record](docs/RELEASE-ACCEPTANCE.md) for tested behavior and remaining account/platform limits.

## Start here

- [Implementation handoff and acceptance criteria](docs/IMPLEMENTER-HANDOFF.md)
- [How to use Company HQ](docs/USAGE.md)
- [What works and what remains](docs/STATUS.md)
- [Native task visibility, computer access and readiness comparison](docs/HQ-READINESS-AND-ACCESS.md)
- [Locked best-of-all stack and staged fallbacks](docs/BEST-STACK.md)
- [Architecture and source map](docs/ARCHITECTURE.md)
- [New upstream candidates: ECC, gstack, Superpowers and the 40-repo list](docs/UPSTREAM-REVIEW.md)
- [Reviewer instructions](docs/REVIEWER.md)
- [Portable setup and isolation](docs/PORTABILITY.md)
- [Packaging provenance](docs/PACKAGING.md)

The desktop includes a conversation, live team view, Beads task board, project editor, native command runner, provider connections and allowance controls. Codex is the fully exercised execution path. Claude Code has an adapter and sign-in flow; authenticated execution must be verified after the user signs in. Kimi Code and Z.ai/GLM have native adapters; see [provider acceptance and boundaries](docs/STATUS.md). Kimi coding entitlement on this machine is still pending. Other detected providers are not represented as executable integrations.

The user talks primarily to the overall supervisor. Useful functional leads and specialists should be allocated according to the actual goal, available account access, complexity and cost. A visible roster is not proof that those agents are running.

## Source layout

| Path | Contents |
| --- | --- |
| `company-hq/` | React/Vite interface, upstream graph and avatars, source archive builder |
| `clawteam/integration/` | Transitional loopback HTTP API, native Codex bridge, compatibility task/inbox adapter, tests, native protocol schemas |
| `ruflo-integration/` | Narrow project-scoped MCP adapter, allowlist and macOS sandbox |
| `codebase-memory-mcp-0.10.8/` | MCP guard/launcher and installation provenance; setup downloads the ignored verified binary; no indexes |
| `teamboard/` | Earlier Swift/macOS audit board and configuration/test utilities |
| root Python files | Transitional model/client discovery, kickoff, reviewed update checks, compatibility wrappers |
| `skills/`, `roles/` | Reusable operating guidance and native role templates when applicable |
| `patches/` | Earlier custom upstream compatibility changes; inactive reference material |
| `catalog.json` | Previously reviewed integration pins and dispositions |
| `docs/repository-candidates.json` | All 40 supplied candidates with observed public metadata; not an activation list |

## Run the app

Open **Company HQ.app** from Applications. Choose **New chat**, describe the result, and send. **Work automatically** is the default; attach a folder with **Add project → Choose folder** when needed. Open **Office** for workers, **Tasks** for the plan, **Files** for the editor/commands, and **Settings** for providers and account allowance.

For an Apple Silicon Mac, install the pinned public preview into `~/Applications` with:

```sh
curl -fsSL https://raw.githubusercontent.com/Dhanunjay-Divi/company-hq/v0.1.3/scripts/install-macos.sh | bash
```

The installer checks the release SHA-256 before replacing an existing app. It does not change provider sign-ins or private chat data. This preview is unsigned and not notarized, so macOS may require manual approval under **System Settings → Privacy & Security** on first open. See [desktop packaging](docs/DESKTOP.md) for the release and manual download path.

To build the macOS app from this checkout, run `python3 scripts/build_desktop.py --dmg`; see [desktop packaging](docs/DESKTOP.md). The standalone core includes its Python runtime. Source development commands below require Python and Node.

## Build and checks

Node 24+ and Python 3.10+ are the starting prerequisites. Setup installs Ruflo's pinned dependency tree with lifecycle scripts disabled and downloads the pinned codebase-memory executable after checksum verification so the reviewed memory/code-intelligence adapters are reproducible. Setup also installs checksum-verified Beads and RTK engines. Native Codex execution and the Ruflo OS sandbox have been verified on macOS; unavailable capabilities are shown in **Settings**. Optional provider packages are described in the provider runtime guide.

For a clean model-free first run:

```sh
python3 scripts/hq.py bootstrap --demo
```

For the normal local workspace after reviewing the setup:

```sh
python3 scripts/hq.py bootstrap
```

Both commands keep runtime state outside this checkout (default: `~/.local/state/company-hq`, or `$XDG_STATE_HOME/company-hq`). They do not rewrite `HOME`/`CODEX_HOME`, copy authentication, start a provider in demo mode, or initialize the attached product repository. See [portable setup](docs/PORTABILITY.md).

From the repository root, run the complete model-free validation suite with:

```sh
python3 scripts/hq.py check
```

That command uses the system interpreter for root utilities and the pinned
`clawteam/venv` interpreter for integration tests, then checks the source
bundle, portability boundaries and truthful capability status.

The original live installation remains a separate deployment target. Running this checkout does not replace it.

## Cost and data

Opening the board does not start an agent. New chats default to **Work automatically**, which permits workspace work while native permission requests still require a decision. Choose **Plan first** for a read-only planning turn and then use **Approve plan & start execution**. Existing planning chats remain in planning until that approval. **Full access** is an explicit per-chat choice: it requests native `dangerFullAccess` with approval policy `never`; native administrator and account policies still apply. Native work uses the existing authorized provider account and may consume its allowance. Company HQ applies a per-workspace reported-token action gate, with no local ceiling by default; an optional limit can be set in Activity. Reported tokens, account allowance and billed money remain distinct; this is not a provider-side billing cap or account-wide quota.

No credentials, Codex conversations, runtime bindings, local task/message databases, user project lists, product files, downloaded binaries, virtual environments or dependency caches are intentionally included.

## License

Company HQ and its original adaptations are AGPL-3.0-only, with upstream notices retained. Agent Teams AI graph/avatar code is copyright © 2026 Илия (777genius). ClawTeam and other dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md). Public visibility does not change third-party license obligations. New candidate repositories have not been copied or activated merely because they appear in the catalog.
