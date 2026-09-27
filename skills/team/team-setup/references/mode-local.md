# team-setup reference: Mode 2 — Point to Existing Local Path

Part of the `team-setup` skill. Load this file only when the user chose Mode 2 (wire an existing local team-ai-directives directory).
Shared context lives in `SKILL.md` (Goal, Input Validation, Mode Selection Flow, Post-Setup checklist).

---

### Mode 2: Point to Existing Local Path

Wire an existing local team-ai-directives directory into the project.

**Explore**:
1. Ask the user for the path to their existing team AI directives directory
2. Validate the path exists
3. Validate the team AI directives structure (same checks as Mode 1 post-clone)
4. If validation fails, explain what's missing and ask the user to fix it or choose a different mode

**Present**:
Show the user:
- Resolved absolute path
- Validation results (which required files/dirs exist and which are missing)

**Confirm**:
```
Use existing team-ai-directives at {ABSOLUTE_PATH}?
[Y/n]
```

**Write/Execute**:
Update the project's `.adlc/init-options.json` to set the `team_ai_directives` field to the resolved path. Uses `jq` for safe JSON manipulation — never interpolate user input into shell source.

```bash
# Resolve to an absolute path and validate (see Input Validation)
ABSOLUTE_PATH="$(realpath "$USER_PATH")"

# Write config using jq (merge into existing or create new)
if [ -f ".adlc/init-options.json" ]; then
  jq --arg p "$ABSOLUTE_PATH" '. + {team_ai_directives: $p}' ".adlc/init-options.json" > ".adlc/init-options.json.tmp" && mv ".adlc/init-options.json.tmp" ".adlc/init-options.json"
else
  jq -n --arg p "$ABSOLUTE_PATH" '{team_ai_directives: $p}' > ".adlc/init-options.json"
fi
```

Ensure the `adlc` orphan branch exists (create if missing):
```bash
git -C "$ABSOLUTE_PATH" show-ref --verify --quiet refs/heads/adlc || {
  cd "$ABSOLUTE_PATH"
  git checkout --orphan adlc
  mkdir -p drafts/cdr reports/sessions reports/projects
  echo '{}' > reports/confidence-scores.json
  touch drafts/cdr/.gitkeep reports/sessions/.gitkeep reports/projects/.gitkeep
  git add -A && git commit -m "Initialize adlc orphan branch (drafts + reports)"
  git checkout main
}
```

*On success: complete Post-Setup Configuration — write `team_ai_directives` to `.adlc/init-options.json`, run the health check (`SKILL.md`), inject `AGENTS.md` (`references/post-setup-agents.md`), install MCP config (`references/post-setup-mcp.md`).*
