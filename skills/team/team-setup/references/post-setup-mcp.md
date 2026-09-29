# team-setup reference: Post-Setup — MCP Config Install

Part of the `team-setup` skill. Load this file only after any setup mode completes, to merge team-declared MCP servers into the project config.
Shared context lives in `SKILL.md` (Goal, Input Validation, Mode Selection Flow, Post-Setup checklist).

---

4. **Install MCP config**: Read `{TEAM_AI_DIRECTIVES}/.mcp.json` if it exists, and merge its `mcpServers` configuration into the project's own `.mcp.json` or `.opencode/mcp.json` config. Report which servers were merged, and highlight any unresolved environment variables needed by the servers.
