---
name: factory-architect
description: Use when orchestrating an architecture lifecycle (specify/init → clarify → implement → analyze) to generate or maintain AD.md.
disable-model-invocation: true
---

# factory-architect

## What this skill does

`factory-architect` orchestrates the architecture-decisions lifecycle. It coordinates individual architecture-related skills (`architect-init`, `architect-specify`, `architect-clarify`, `architect-implement`, `architect-analyze`) to maintain a consistent `AD.md` at the project root.

It operates as a **Kind-A DAG orchestrator** in alignment with the shared executor engine contract in `factory-mission/references/executor.md`.

---

## When to use

- You want to bootstrap, refine, or analyze a project's system-level design and decisions (ADRs) end-to-end.
- You want to verify that architectural viewpoints conform to the Rozanski & Woods methodology.

**When NOT to use**:
- For product-requirements definition (use `factory-product` instead).
- For feature-level software execution (use `factory-mission` instead).

---

## Execution Mechanism — drive this in-session, never recurse `workflow run`

This skill's own steps (below) are defined in `workflow.yml` for the **headless**
executor (`adlc-cli workflow run <path>`, used by CI/sensor-triggered runs with
no live model in the loop). When YOU are running this skill — i.e. any time you
reached this file via a skill/command invocation inside an active session —
you ARE the executor. Drive these steps yourself, inline, using
`adlc-cli workflow state start|advance|pause|fail|show` (see `adlc-cli workflow
state --help`) to persist progress, not by shelling out to a second
`adlc-cli workflow run factory-architect` (or any bare skill name).

Confirmed broken if you try it anyway: `workflow run` resolves a bare name
only against a literal `.yml`/`.yaml` path, `.adlc/workflows/<id>/workflow.yml`
(an "installed" copy), or a short hardcoded builtin list (`factory` only) —
never against `.agents/skills/<id>/workflow.yml`, which is where this file
actually lives once installed. A nested `workflow run factory-architect` call
fails immediately with `Workflow not found: factory-architect` — don't retry
it with a guessed path or extra flags; drive the steps yourself instead, e.g.:

```
adlc-cli workflow state start --workflow .agents/skills/factory-architect/workflow.yml --run-id <run-id> --input route=brownfield
# ... do the specify step's actual work yourself (write ADR drafts), then:
adlc-cli workflow state advance <run-id> --step specify --status completed
```

`state advance` only accepts the **top-level** step ids in `workflow.yml`:
`specify`, `clarify`, `gate-decisions`, `build-and-verify`. The nested
`implement` / `analyze` steps are not valid ids (`Unknown step 'implement'`).
Two steps need more than a bare `advance`:

- `gate-decisions` is a human gate. Don't advance it directly:
  `adlc-cli workflow state pause <run-id> --step gate-decisions`, ask the
  human to approve or reject, then
  `adlc-cli workflow state advance <run-id> --step gate-decisions --status completed --output-json '{"choice":"approve"}'`.
- `build-and-verify` is a do-while loop (max 3 iterations) that the state
  helper does not evaluate. Run `implement` then `analyze` yourself; if the
  analyze output contains `VERDICT: CRITICAL` or `VERDICT: HIGH`, repeat.
  When the loop ends, advance once:
  `adlc-cli workflow state advance <run-id> --step build-and-verify --status completed --output-json '{"stdout":"VERDICT: PASS"}'`.

See `factory-mission/references/executor.md` for the full gate and output contract.

---

## Lifecycle DAG & Step Resolution

`factory-architect` implements a **fixed named-skill DAG** (`fixed` step resolution):

### Greenfield Route (default on empty project)
1. **`specify`** (`generate` phase) -> Invoke `architect-specify` to collaboratively capture ADR drafts in `.adlc/drafts/adr/`.
2. **`clarify`⭐** (`clarify` phase) -> Invoke `architect-clarify` to run interactive quality checks and mark ADRs Accepted (human sign-off gate).
3. **`implement`** (`build` phase) -> Invoke `architect-implement` to compile accepted ADRs into `AD.md` (by sub-systems) and promote them to `docs/adlc/memory/adr/`.
4. **`analyze`** (`analyze` phase) -> Invoke `architect-analyze` to verify AD/ADR consistency and output a severity-ranked report.

### Brownfield Route (default if code exists but no ADRs)
1. **`init`** (`generate` phase) -> Invoke `architect-init` to reverse-engineer draft ADRs from the existing architecture.
2. **`clarify`⭐** → **`implement`** → **`analyze`** (same as Greenfield).

### Refresh Route (default if AD.md and memory ADRs already exist)
1. **`analyze`** (`analyze` phase) -> Run architect-analyze first to detect drift.
2. **`clarify`⭐** → **`implement`** → **`analyze`** (drift-correction cycle).

---

## Shared Executor Overrides

`factory-architect` overrides the shared executor engine primitives as follows:

1. **Publish Target**: Fixed to `local`. Outputs are written to `docs/adlc/memory/adr/` and `docs/adlc/architect/AD.md`. If tracker-integrated, a `tracker` completion summary comment is also posted.
2. **Output Types**: Steps use the following `output_type` assignments:
   - `specify`/`init` → `draft` (ADR drafts stay in `.adlc/drafts/adr/`, not published to comment bus)
   - `clarify`⭐ → `decision` (accepted/rejected ADR list published to comment bus)
   - `implement` → `artifact-ref` (AD.md path reference published, content stays on disk)
   - `analyze` → `findings` (severity-ranked consistency report published to comment bus)
3. **Correction Loop**: If `analyze` returns `CRITICAL` or `HIGH` consistency errors, the executor routes back to `clarify` with the analyze marker in `reads_from`. `clarify` reads the findings from the PR/MR/issue comment bus (or local fallback). This loop is bounded by `max_corrections` (default 2); if exceeded, the orchestrator halts for human review.
4. **Supervision Default**: `hybrid`. A human gate is hard-enforced at `clarify`⭐ (for ADR approvals) and at final `AD.md` review.
5. **Pre-flight Check**: Verifies that the `architect-*` lifecycle skills are installed in the workspace before beginning Phase 0.
