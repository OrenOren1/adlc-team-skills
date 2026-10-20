"""The change-clarify loader must see every pending ChDR.

A ChDR draft carries its status in YAML frontmatter (the canonical draft
template) or, in a full record, in a "### Status: **X**" heading. The
setup script matched only the heading form, so it reported "no pending
ChDRs" for drafts written from the template — including the ones
team-boot's continuous capture produces, and including every ChDR this
workspace holds. A review gate that cannot see the record it is meant to
review is silently inert.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
BASH = ROOT / "skills/change/change-clarify/scripts/bash/setup-change-clarify.sh"
PS1 = ROOT / "skills/change/change-clarify/scripts/powershell/setup-change-clarify.ps1"

FRONTMATTER_DRAFT = """\
---
status: proposed
date: 2026-10-20
type: incident
---

# ChDR-900: a draft written from the canonical template

## Context
Something happened.
"""

HEADING_DRAFT = """\
# ChDR-901: a full record with a status heading

### Status: **Proposed**

## Context
Something happened.
"""

ACCEPTED_DRAFT = """\
---
status: accepted
date: 2026-10-19
---

# ChDR-902: an accepted draft
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".adlc" / "drafts" / "chdr").mkdir(parents=True)
    return tmp_path


def write(project, name, body):
    (project / ".adlc" / "drafts" / "chdr" / name).write_text(body, encoding="utf-8")


def run_bash(project):
    proc = subprocess.run(
        ["bash", str(BASH)], cwd=project, capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_frontmatter_status_drafts_are_pending(project):
    write(project, "ChDR-900-frontmatter.md", FRONTMATTER_DRAFT)
    out = run_bash(project)
    assert out["PENDING_CHDRS"] == 1, out
    assert out["ACCEPTED_CHDRS"] == 0, out
    assert out["EXISTING_CHDRS"] == 1, out


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_heading_status_drafts_are_pending(project):
    write(project, "ChDR-901-heading.md", HEADING_DRAFT)
    out = run_bash(project)
    assert out["PENDING_CHDRS"] == 1, out


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_accepted_drafts_are_not_pending(project):
    write(project, "ChDR-902-accepted.md", ACCEPTED_DRAFT)
    out = run_bash(project)
    assert out["ACCEPTED_CHDRS"] == 1, out
    assert out["PENDING_CHDRS"] == 0, out


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_both_status_forms_count(project):
    write(project, "ChDR-900-frontmatter.md", FRONTMATTER_DRAFT)
    write(project, "ChDR-901-heading.md", HEADING_DRAFT)
    write(project, "ChDR-902-accepted.md", ACCEPTED_DRAFT)
    out = run_bash(project)
    assert out["PENDING_CHDRS"] == 2, out
    assert out["ACCEPTED_CHDRS"] == 1, out
    assert out["EXISTING_CHDRS"] == 3, out


def test_powershell_twin_reads_the_same_forms():
    """The bash and PowerShell setup scripts must agree (same stem, same JSON)."""
    text = PS1.read_text(encoding="utf-8")
    assert "status:" in text, "the PowerShell twin must read the frontmatter status"
    assert "### Status" in text, "the PowerShell twin must read the heading status"
