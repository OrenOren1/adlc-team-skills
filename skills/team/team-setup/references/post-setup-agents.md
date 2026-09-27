# team-setup reference: Post-Setup — Project AGENTS.md Injection

Part of the `team-setup` skill. Load this file only after any setup mode completes, to inject the project-level `AGENTS.md` directive.
Shared context lives in `SKILL.md` (Goal, Input Validation, Mode Selection Flow, Post-Setup checklist).

---

3. Inject the project-level `AGENTS.md` directive so agents auto-invoke `team-boot` at session start:

```bash
# Bash
bash "$(dirname "$0")/team-helpers.sh" --inject-agents "{PROJECT_ROOT}"

# PowerShell
pwsh "$(Split-Path $PSCommandPath -Parent)/team-helpers.ps1" -InjectAgents "{PROJECT_ROOT}"
```

This creates or updates the project's `AGENTS.md` with a managed section (between `<!-- TEAM_AI_DIRECTIVES START -->` and `<!-- TEAM_AI_DIRECTIVES END -->` markers) containing:

- **Event-hook awareness**: notes that `team-boot` runs automatically at session start via the event hook (for agents with event support), injecting a lean orientation into the first user message.
- **Fallback invocation**: "If the team AI directives context is NOT in your system prompt or first user message (agent without event support), invoke the `team-boot` skill before responding to any task or question."
- **Unconfigured handling**: "If team AI directives are unconfigured, invoke the `team-setup` skill."
- **Team Context in Use contract**: "Every response MUST include a Team Context in Use section before the task answer" — a 4-column table (`ID | Name | Type | Rel`) listing genuinely matched CDRs/skills, followed by `_Searched N CDRs, M skills, J matched._`

Without this section, an agent without event support has no session-start instruction to load team context, and the team AI directives repository remains invisible until manually loaded. The section is idempotent: re-running `team-setup` or `team-repair` updates the section in place without duplicating content.
