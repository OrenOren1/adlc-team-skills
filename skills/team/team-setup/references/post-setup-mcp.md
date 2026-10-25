# team-setup reference: Post-Setup — MCP Config Install

Part of the `team-setup` skill. Load this file only after any setup mode completes, to merge team-declared MCP servers into the project config.
Shared context lives in `SKILL.md` (Goal, Input Validation, Mode Selection Flow, Post-Setup checklist).

---

5. **Install MCP config**: if `{TEAM_AI_DIRECTIVES}/.mcp.json` exists, merge its `mcpServers` into the project's agent config by running the helper. **Do not hand-merge or write your own merge script.** Each agent reads a different shape, and a verbatim copy breaks the agent at startup.

```bash
# Bash (agent defaults to .adlc/init-options.json "agent", else claude)
bash "$(dirname "$0")/scripts/bash/team-helpers.sh" --install-mcp "{PROJECT_ROOT}" [--agent opencode]

# PowerShell
pwsh "$(Split-Path $PSCommandPath -Parent)/scripts/powershell/team-helpers.ps1" -InstallMcp "{PROJECT_ROOT}" [-Agent opencode]
```

What the helper writes, per agent:

| Agent | Target | Entry shape |
|---|---|---|
| `opencode` | `opencode.json`, or `.opencode/opencode.json` if that is the file that exists, under the `mcp` key | `{"type": "local", "command": ["<command>", ...args], "environment": {...}, "enabled": true}`, or `{"type": "remote", "url": ..., "headers": {...}, "enabled": true}` for URL servers. `${VAR}` becomes `{env:VAR}` |
| any other (`claude`, …) | `.mcp.json`, under `mcpServers` | verbatim `.mcp.json` entry |

Why the translation matters: OpenCode rejects the `.mcp.json` shape (`{"command": "npx", "args": [...]}`) with `Configuration is invalid ... Expected { type: "local" } | { type: "remote" } ... mcp.<name>`, and then refuses to start. Every headless run in that workspace fails before the agent does any work. It also expands only `{env:VAR}`, so a copied `${VAR}` would reach the server as a literal string.

Merge rules:
- A server already present in the target agent's shape is kept untouched. For OpenCode that includes a bare `{"enabled": false}` (or `true`) entry, which switches a server defined elsewhere on or off.
- An entry in the wrong shape is **repaired**, i.e. replaced with the translated entry. This fixes configs left by an earlier verbatim merge.
- Other keys in the file (`$schema`, `plugin`, …) are preserved. Re-running is idempotent.
- A `.jsonc` config is not edited. The helper says so, and you add the servers by hand.
- If `.adlc/init-options.json` has `"team_ai_directives": null` (the opt-out marker), nothing is installed.

The helper needs `python3` **or** `node` (it uses whichever is on `PATH`; `npx skills` already requires node, and the agentic-container image ships node but no `python3`). If neither is available it exits non-zero with `team-helpers needs python3 or node` rather than silently skipping. Do not replace it with your own script; report the error.

Report the helper's output lines (`merged` / `kept` / `repaired`) and its final `set these env vars …` line, which lists the variables the merged servers need that are not set in the current environment.
