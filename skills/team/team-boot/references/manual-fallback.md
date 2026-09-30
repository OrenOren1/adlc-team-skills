# team-boot reference: Manual fallback (agents without event support)

Part of the `team-boot` skill. Load this file only when the team AI
directives context is NOT in your system prompt or first user message
(agent without event support). Shared context (Class Boots catalog,
Decision Capture ledger contract) lives in `SKILL.md`.

---

## Manual fallback (agents without event support)

1. Read `.adlc/init-options.json` from the current working directory.
   Do NOT walk up parent directories. Do NOT use glob, find, or any
   file-search tool to locate it.
2. If unconfigured (missing, `null`, or path doesn't exist): invoke the
   `team-setup` skill.
3. If configured: read and assemble the constitution, CDR.md index table,
   and `.skills.json` into your context. Present the Class Boots catalog
   above and follow it: invoke the matching class boot when a task or
   decision matches a row.
4. The CDR index is your catalog — read full module bodies on demand
   when a task matches a CDR descriptor (or invoke `team-levelup` to do
   it as a structured deep-dive).
