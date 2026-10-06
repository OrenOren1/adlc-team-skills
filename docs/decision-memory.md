# Decision Memory — Where ADRs/PDRs Live

This repository keeps **no ADR/PDR memory of its own**. Decision records for
this project live exclusively in the parent workspace:

- **Workspace memory**: `docs/adlc/memory/` in `adlc-workspace`
  (`adr/` for architecture decisions, `pdr/` for product decisions)

Policy: workspace ADR-412 (workspace-centralized decision memory). Rationale:
per-submodule memories produced colliding ID sequences (this repo's legacy
`.adlc/memory/` ADR-317–326 duplicated different decisions than the
workspace's same-numbered records) and format drift. `.adlc/` is gitignored
here — any records created under it exist only on local disk and will not be
reviewed or merged.

## Record map (pre-centralization `.adlc/memory/` → workspace)

The 18 ADRs + 14 PDRs formerly kept here map to workspace records as follows.
All duplicates were verified semantically (decision-statement spot-check) before
removal; unique records were imported with new workspace IDs.

| Former record | Workspace equivalent | Relation |
|--|--|--|
| ADR-317 stateless queue | ADR-317 | same decision |
| ADR-318 label gate | ADR-318 | same decision |
| ADR-319 comment bus | ADR-330 | relocated |
| ADR-320 worker brief | ADR-331 | relocated |
| ADR-321 worktree isolation | ADR-332 | relocated |
| ADR-322 lease TTL | ADR-333 | relocated |
| ADR-323 stall detection | ADR-334 | relocated |
| ADR-324 exact-head review | ADR-335 | relocated |
| ADR-325 lanes | ADR-336 | relocated |
| ADR-326 runtime independence | ADR-337 | relocated |
| ADR-338…345 (8 records) | ADR-338…345 | same decisions |
| PDR-020 planning mode | PDR-020 | duplicate |
| PDR-021 cleanup bot | PDR-021 | duplicate |
| PDR-030 agent-authored stamp | **PDR-108** (new) | unique — imported |
| PDR-040 findings→directives | PDR-040 | subsumed (twice-mistake class) |
| PDR-048…056 (9 records) | PDR-048…056 | duplicates |
| PDR-057 deck↔code terminology | **PDR-109** (new) | unique — imported |

## Working with decisions

- **Reading**: class boots resolve memory from the current working directory and
  fall back to the workspace root (detected via `.gitmodules`) when no local
  memory exists.
- **Writing**: draft new decisions to the **workspace root** `.adlc/drafts/`
  and promote to workspace `docs/adlc/memory/` — never under this repo's
  `.adlc/`.
