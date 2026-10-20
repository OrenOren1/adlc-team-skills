---
name: factory-product
description: Use when orchestrating a product lifecycle (specify/init → clarify → implement → analyze) to generate or verify PRD.md.
disable-model-invocation: true
---

# factory-product

## What this skill does

`factory-product` orchestrates the product-decisions lifecycle. It coordinates individual product-related skills (`product-init`, `product-specify`, `product-clarify`, `product-implement`, `product-analyze`) to maintain a consistent `PRD.md` at `docs/adlc/product/PRD.md` (the shared layout).

It operates as a **Kind-A DAG orchestrator** in alignment with the shared executor engine contract in `factory-mission/references/executor.md`.

---

## When to use

- You want to bootstrap, refine, or analyze a product's requirements and decisions (PDRs) end-to-end.
- You want a guided, accept-gated, and verified product definition process with a resume checkpoint.

**When NOT to use**:
- For software implementation task execution (use `factory-mission` instead).
- For architecture decision records (use `factory-architect` instead).

---

## Lifecycle DAG & Step Resolution

`factory-product` implements a **fixed named-skill DAG** (`fixed` step resolution):

### Greenfield Route (default on empty project)
1. **`specify`** (`generate` phase) -> Invoke `product-specify` to collaboratively capture PDR drafts in `.adlc/drafts/pdr/`.
2. **`clarify`⭐** (`clarify` phase) -> Invoke `product-clarify` to run interactive quality checks and mark PDRs Accepted (human sign-off gate).
3. **`implement`** (`build` phase) -> Invoke `product-implement` to compile accepted PDRs into `docs/adlc/product/PRD.md` and promote them to `docs/adlc/memory/pdr/`.
4. **`analyze`** (`analyze` phase) -> Invoke `product-analyze` to verify PRD/PDR consistency and output a severity-ranked report.

### Brownfield Route (default if code exists but no PDRs)
1. **`init`** (`generate` phase) -> Invoke `product-init` to reverse-engineer draft PDRs from the existing codebase.
2. **`clarify`⭐** → **`implement`** → **`analyze`** (same as Greenfield).

### Refresh Route (default if PRD.md and memory PDRs already exist)
1. **`analyze`** (`analyze` phase) -> Run product-analyze first to detect drift.
2. **`clarify`⭐** → **`implement`** → **`analyze`** (drift-correction cycle).

---

## Shared Executor Overrides

`factory-product` overrides the shared executor engine primitives as follows:

1. **Publish Target**: Fixed to `local`. Outputs are written to `docs/adlc/memory/pdr/` and `docs/adlc/product/PRD.md`. If tracker-integrated, a `tracker` completion summary comment is also posted.
2. **Output Types**: Steps use the following `output_type` assignments:
   - `specify`/`init` → `draft` (PDR drafts stay in `.adlc/drafts/pdr/`, not published to comment bus)
   - `clarify`⭐ → `decision` (accepted/rejected PDR list published to comment bus)
   - `implement` → `artifact-ref` (PRD.md path reference published, content stays on disk)
   - `analyze` → `findings` (severity-ranked consistency report published to comment bus)
3. **Correction Loop**: If `analyze` returns `CRITICAL` or `HIGH` consistency errors, the executor routes back to `clarify` with the analyze marker in `reads_from`. `clarify` reads the findings from the PR/MR/issue comment bus (or local fallback). This loop is bounded by `max_corrections` (default 2); if exceeded, the orchestrator halts for human review.
4. **Supervision Default**: `hybrid`. A human gate is hard-enforced at `clarify`⭐ (for PDR approvals) and at final `PRD.md` review.
5. **Pre-flight Check**: Verifies that the `product-*` lifecycle skills are installed in the workspace before beginning Phase 0.

---

## Run Branch, Step Commits and Draft MR (ADR-431, ADR-431-amendment, ADR-444)

**Requires:** the `factory-mission` skill (provides the run helpers): `adlc-cli skills add tikalk/adlc-team-skills --skill factory-mission`

In a factory run (`ADLC_RUN_ID` set by the workflow engine) this orchestrator — and only it, never the `product-*` lifecycle skills — commits, pushes the run branch and opens the draft MR, always through these three helpers:

1. **Before the first step:** `bash {REPO_ROOT}/.agents/skills/factory-mission/scripts/bash/run-branch.sh` — checks out `factory/<repo>-<iid>` (from `ADLC_ISSUE_REF`) in the project root, reusing it or continuing from `origin`. Shared with the other intent lane and with re-dispatches.
2. **After each step** (`specify`/`init`, `clarify`, `implement`, `analyze` fixes):
   `bash {REPO_ROOT}/.agents/skills/factory-mission/scripts/bash/commit-step.sh --orchestrator factory-product --step <step> --output-type <draft|decision|artifact-ref|findings> --summary "<one line, no issue text>" --records <IDs> -- <paths the step wrote>`
   Pass only paths the step wrote, inside the ADR-433 allowlist (`.adlc/drafts/pdr/`, `docs/adlc/memory/pdr/`, `docs/adlc/product/PRD.md`, `.adlc/product/sections/`, `.adlc/product/state.json`). It prints `sha: <sha>` or `sha: none`; put that `sha` in the step's bus marker (ADR-431 §3). Never stage `.adlc/workflows/**`.
3. **At the end:** `bash {REPO_ROOT}/.agents/skills/factory-mission/scripts/bash/open-mr.sh` — pushes the run branch only, finds or opens one draft MR (merge commit, no squash; milestone/assignee per ADR-432) and writes `mr_url` to `ADLC_STEP_OUTPUT`, which the engine's gate links (`context.link`). Also write a one-line `conclusion` into the same JSON object if you have one (ADR-391-amendment-2 §4).

Outside a factory run the helpers do nothing unless the user opted in (`adlc.commit_steps: true` in `.adlc/init-options.json`, or `--commit` passed to this skill, which you forward to `commit-step.sh`); `run-branch.sh` and `open-mr.sh` never act without `ADLC_RUN_ID`. A helper's non-zero exit (refused path, missing committer identity, tracker scope) stops the run — report it, do not work around it.
