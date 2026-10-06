---
name: factory-product
description: Use when orchestrating a product lifecycle (specify/init → clarify → implement → analyze) to generate or verify PRD.md.
disable-model-invocation: true
---

# factory-product

## What this skill does

`factory-product` orchestrates the product-decisions lifecycle. It coordinates individual product-related skills (`product-init`, `product-specify`, `product-clarify`, `product-implement`, `product-analyze`) to maintain a consistent `PRD.md` at `docs/adlc/product/PRD.md` (ADR-401).

It operates as a **Kind-A DAG orchestrator** in alignment with the shared executor engine contract in `factory-mission/references/executor.md`.

---

## When to use

- You want to bootstrap, refine, or analyze a product's requirements and decisions (PDRs) end-to-end.
- You want a guided, accept-gated, and verified product definition process with a resume checkpoint.

**When NOT to use**:
- For software implementation task execution (use `factory-mission` instead).
- For architecture decision records (use `factory-architect` instead).

---

## Execution Mechanism — drive this in-session, never recurse `workflow run`

This skill's own steps (below) are defined in `workflow.yml` for the **headless**
executor (`adlc-cli workflow run <path>`, used by CI/sensor-triggered runs with
no live model in the loop). When YOU are running this skill — i.e. any time you
reached this file via a skill/command invocation inside an active session —
you ARE the executor. Drive these steps yourself, inline, using
`adlc-cli workflow state start|advance|pause|fail|show` (see `adlc-cli workflow
state --help`) to persist progress, not by shelling out to a second
`adlc-cli workflow run factory-product` (or any bare skill name).

Confirmed broken if you try it anyway: `workflow run` resolves a bare name
only against a literal `.yml`/`.yaml` path, `.adlc/workflows/<id>/workflow.yml`
(an "installed" copy), or a short hardcoded builtin list (`factory` only) —
never against `.agents/skills/<id>/workflow.yml`, which is where this file
actually lives once installed. A nested `workflow run factory-product` call
fails immediately with `Workflow not found: factory-product` — don't retry
it with a guessed path or extra flags; drive the steps yourself instead, e.g.:

```
adlc-cli workflow state start --workflow .agents/skills/factory-product/workflow.yml --run-id <run-id> --input route=brownfield
# ... do the specify step's actual work yourself (write PDR drafts), then:
adlc-cli workflow state advance <run-id> --step specify --status completed
```

Use the real step ids from this file's `steps:` list below (`specify`,
`clarify`, `gate-decisions`, `implement`, `analyze`) — not guessed ones.

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
