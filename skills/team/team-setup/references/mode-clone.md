# team-setup reference: Mode 1 — Clone from GitHub

Part of the `team-setup` skill. Load this file only when the user chose Mode 1 (clone an existing team-ai-directives repository from GitHub).
Shared context lives in `SKILL.md` (Goal, Input Validation, Mode Selection Flow, Post-Setup checklist).

---

### Mode 1: Clone from GitHub

Clone an existing team-ai-directives repository from GitHub.

**Explore**:
1. Ask the user for the GitHub repository URL (default: `https://github.com/tikalk/agentic-sdlc-team-ai-directives`)
2. Validate the URL starts with `https://` (reject `file://`, `ssh://`, and other schemes — see Input Validation). Only clone repositories you trust; the cloned content is read by agents later.
3. Ask where to clone it (default: `./team-ai-directives`)
4. Check that the destination does not already exist

**Present**:
Show the user:
- Source URL
- Destination path
- Estimated size (from remote repo info if available)

**Confirm**:
```
Clone team-ai-directives from {URL} to {DEST}?
[Y/n]
```

**Write/Execute**:
```bash
git clone "{URL}" "{DEST}"
```

After clone, verify the team AI directives structure exists:
- `{DEST}/context_modules/constitution.md`
- `{DEST}/context_modules/rules/`
- `{DEST}/context_modules/personas/`
- `{DEST}/context_modules/examples/`
- `{DEST}/CDR.md`
- `{DEST}/.skills.json`

Verify the `adlc` orphan branch exists (for CDR drafts and usage reports), create if missing:
```bash
git -C "{DEST}" show-ref --verify --quiet refs/heads/adlc || {
  cd "{DEST}"
  git checkout --orphan adlc
  mkdir -p drafts/cdr reports/sessions reports/projects
  echo '{}' > reports/confidence-scores.json
  touch drafts/cdr/.gitkeep reports/sessions/.gitkeep reports/projects/.gitkeep
  git add -A && git commit -m "Initialize adlc orphan branch (drafts + reports)"
  git checkout main
}
```

*On success: complete Post-Setup Configuration — write `team_ai_directives` to `.adlc/init-options.json`, run the health check (`SKILL.md`), inject `AGENTS.md` (`references/post-setup-agents.md`), install MCP config (`references/post-setup-mcp.md`).*
