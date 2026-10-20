"""Mermaid syntax validator (ADR-434) — corpus, severity, location, read-only.

The validator is a deterministic static scan over ```mermaid fenced blocks:
one finding per broken block, each carrying a severity, a location and a
suggested patch. These tests pin the rule set once so product-analyze and
architect-analyze can reference it instead of forking the prose (ADR-434
mitigation for rule drift).
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
LINTER = ROOT / "skills/architect/architect-clarify/scripts/bash/mermaid-lint.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash not available"
)


def run_linter(tmp_path, text, *args):
    """Run the linter over one artifact; return (exit_code, findings).

    The machine channel is tab-separated: severity, rule, file, line, fence,
    message, offending line, suggested patch.
    """
    artifact = tmp_path / "artifact.md"
    artifact.write_text(text, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(LINTER), "--tsv", str(artifact), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    fields = ("severity", "rule", "file", "line", "fence", "message", "offending", "suggestion")
    findings = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        assert len(parts) == len(fields), f"malformed TSV row: {line!r}"
        record = dict(zip(fields, parts))
        record["line"] = int(record["line"])
        record["fence"] = int(record["fence"])
        findings.append(record)
    return proc.returncode, findings


def rules(findings):
    return [f["rule"] for f in findings]


# ── the linter exists and is executable-by-bash ─────────────────────────────

def test_linter_is_present():
    assert LINTER.exists(), f"canonical mermaid linter missing at {LINTER}"


# ── broken corpus: one finding per broken block, with location + patch ─────

BROKEN = """\
# Broken corpus

## graph keyword (style, renderable)

```mermaid
graph TD
  A --> B
```

## empty body

```mermaid
flowchart TD
```

## malformed gantt header

```mermaid
gantt
  this line is not a gantt key
```

## empty block

```mermaid
```

## unclosed fence (truncated file — the block is never closed)

```mermaid
flowchart TD
  A --> B
"""


def test_broken_corpus_finds_every_broken_block(tmp_path):
    code, findings = run_linter(tmp_path, BROKEN)
    assert code == 1, "a HIGH (syntax-break) must set exit code 1"
    found = rules(findings)
    for expected in (
        "M001-fence-not-closed",
        "M009-non-mandated-keyword",
        "M005-empty-body",
        "M006-malformed-gantt-header",
        "M004-empty-block",
    ):
        assert expected in found, f"expected rule {expected} in {found}"


def test_syntax_breaks_are_high_and_style_is_medium(tmp_path):
    _, findings = run_linter(tmp_path, BROKEN)
    by_rule = {f["rule"]: f for f in findings}
    for rule in (
        "M001-fence-not-closed",
        "M004-empty-block",
        "M005-empty-body",
        "M006-malformed-gantt-header",
    ):
        assert by_rule[rule]["severity"] == "HIGH", f"{rule} must be HIGH"
    assert by_rule["M009-non-mandated-keyword"]["severity"] == "MEDIUM", (
        "'graph' renders — a style finding, not a syntax break"
    )


def test_every_finding_carries_location_and_a_suggested_patch(tmp_path):
    _, findings = run_linter(tmp_path, BROKEN)
    assert findings, "expected findings"
    for f in findings:
        assert f["file"].endswith("artifact.md")
        assert isinstance(f["line"], int) and f["line"] >= 1, "location line missing"
        assert isinstance(f["fence"], int) and f["fence"] >= 1, "fence index missing"
        assert f["suggestion"].strip(), f"no suggested patch for {f['rule']}"
        assert f["offending"].strip(), f"no offending line for {f['rule']}"


def test_fence_index_counts_blocks_in_order(tmp_path):
    _, findings = run_linter(tmp_path, BROKEN)
    fences = [f["fence"] for f in findings]
    assert fences == sorted(fences), "fence indices must be in document order"
    assert fences[0] == 1, "the first broken block is fence #1"
    assert fences[-1] == 5, "the truncated trailing block is the last fence"


# ── valid corpus: zero findings ─────────────────────────────────────────────

VALID = """\
# Valid corpus

```mermaid
flowchart TD
  A[Start] --> B[End]
```

```mermaid
sequenceDiagram
  participant A
  A->>B: hello
```

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
```

```mermaid
gantt
  dateFormat YYYY-MM-DD
  section S1
  Task :a1, 2026-01-01, 3d
```

```mermaid
journey
  title My day
  section Go
    Make tea: 5: Me
```
"""


def test_valid_corpus_has_no_findings(tmp_path):
    code, findings = run_linter(tmp_path, VALID)
    assert findings == [], f"valid corpus must not be flagged: {findings}"
    assert code == 0, "a clean scan must exit 0"


def test_indented_diagram_lines_are_accepted(tmp_path):
    """A diagram body is normally indented — the type keyword must still be
    recognised, and an indented statement must not read as an empty body."""
    text = "```mermaid\n  flowchart TD\n    A --> B\n```\n"
    code, findings = run_linter(tmp_path, text)
    assert findings == [], f"indented valid block must not be flagged: {findings}"
    assert code == 0


# ── unknown type: MEDIUM, never a false HIGH (ADR-434) ─────────────────────

def test_unknown_diagram_type_is_medium_not_high(tmp_path):
    text = "```mermaid\nsomeFutureDiagram\n  whatever\n```\n"
    code, findings = run_linter(tmp_path, text)
    assert len(findings) == 1
    assert findings[0]["rule"] == "M002-unknown-diagram-type"
    assert findings[0]["severity"] == "MEDIUM", "unknown type must never be a false HIGH"
    assert code == 2, "MEDIUM-only findings exit 2"


# ── read-only contract (ADR-433 lifecycle write scope) ─────────────────────

def test_linter_does_not_modify_the_artifact(tmp_path):
    artifact = tmp_path / "artifact.md"
    artifact.write_text(BROKEN, encoding="utf-8")
    before = hashlib.sha256(artifact.read_bytes()).hexdigest()
    listing_before = sorted(p.name for p in tmp_path.iterdir())
    subprocess.run(
        ["bash", str(LINTER), "--tsv", str(artifact)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    after = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert before == after, "the lint pass must not write to the artifact"
    assert sorted(p.name for p in tmp_path.iterdir()) == listing_before, (
        "the lint pass must not create files"
    )


def test_linter_is_deterministic(tmp_path):
    first = run_linter(tmp_path, BROKEN)[1]
    second = run_linter(tmp_path, BROKEN)[1]
    assert first == second, "the same input must yield the same findings"


# ── usage errors ───────────────────────────────────────────────────────────

def test_missing_file_is_a_usage_error(tmp_path):
    proc = subprocess.run(
        ["bash", str(LINTER), str(tmp_path / "nope.md")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 3, "a missing file must not be reported as a finding"


def test_no_arguments_is_a_usage_error():
    proc = subprocess.run(
        ["bash", str(LINTER)], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 3
