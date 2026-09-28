"""No-stale-copies + borrower-reference guards for consolidated shared helpers.

setup-architect.{sh,ps1} (+ common/ascii/mermaid companions) and pdr-lib.{sh,ps1}
are canonical in exactly one skill each; every other skill references them by
path. This pins that contract: stale copies must not reappear, borrower
references must resolve in BOTH the source tree (skills/<group>/<skill>/) and
the installed mirror tree (.agents/skills/<skill>/, flat per skill).
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
MIRROR = ROOT / ".agents" / "skills"

# Canonical home per helper basename.
CANONICAL = {
    "setup-architect.sh": ROOT / "skills/architect/architect-clarify/scripts/bash/setup-architect.sh",
    "setup-architect.ps1": ROOT / "skills/architect/architect-clarify/scripts/powershell/setup-architect.ps1",
    "common.sh": ROOT / "skills/architect/architect-clarify/scripts/bash/common.sh",
    "ascii-generator.sh": ROOT / "skills/architect/architect-clarify/scripts/bash/ascii-generator.sh",
    "ASCII-Generator.ps1": ROOT / "skills/architect/architect-clarify/scripts/powershell/ASCII-Generator.ps1",
    "mermaid-generator.sh": ROOT / "skills/architect/architect-clarify/scripts/bash/mermaid-generator.sh",
    "Mermaid-Generator.ps1": ROOT / "skills/architect/architect-clarify/scripts/powershell/Mermaid-Generator.ps1",
    "pdr-lib.sh": ROOT / "skills/product/product-clarify/scripts/bash/pdr-lib.sh",
    "pdr-lib.ps1": ROOT / "skills/product/product-clarify/scripts/powershell/pdr-lib.ps1",
}

# (borrower script, expected canonical-relative snippet in its source line)
BASH_BORROWERS = {
    ROOT / "skills/product/product-implement/scripts/bash/setup-product-implement.sh": "../../../product-clarify/scripts/bash/pdr-lib.sh",
    ROOT / "skills/product/product-init/scripts/bash/setup-product-init.sh": "../../../product-clarify/scripts/bash/pdr-lib.sh",
    ROOT / "skills/product/product-specify/scripts/bash/setup-product-specify.sh": "../../../product-clarify/scripts/bash/pdr-lib.sh",
    ROOT / "skills/product/product-implement/scripts/bash/migrate-pdr-frontmatter.sh": "../../../product-clarify/scripts/bash/pdr-lib.sh",
}

# (SKILL.md, canonical mirror-absolute path it must reference)
DOC_BORROWERS = {
    ROOT / "skills/architect/architect-analyze/SKILL.md":
        "{REPO_ROOT}/.agents/skills/architect-clarify/scripts/bash/setup-architect.sh",
    ROOT / "skills/architect/architect-implement/SKILL.md":
        "{REPO_ROOT}/.agents/skills/architect-clarify/scripts/bash/setup-architect.sh",
    ROOT / "skills/architect/architect-init/SKILL.md":
        "{REPO_ROOT}/.agents/skills/architect-clarify/scripts/bash/setup-architect.sh",
    ROOT / "skills/architect/architect-specify/SKILL.md":
        "{REPO_ROOT}/.agents/skills/architect-clarify/scripts/bash/setup-architect.sh",
    ROOT / "skills/product/product-implement/SKILL.md":
        "{REPO_ROOT}/.agents/skills/product-clarify/scripts/bash/pdr-lib.sh",
}

STALE_ARCHITECT_DIRS = [
    "architect-analyze", "architect-implement", "architect-init", "architect-specify",
]
STALE_ARCHITECT_FILES = [
    "setup-architect.sh", "setup-architect.ps1", "common.sh",
    "ascii-generator.sh", "ASCII-Generator.ps1",
    "mermaid-generator.sh", "Mermaid-Generator.ps1",
]
STALE_PRODUCT_DIRS = ["product-implement", "product-init", "product-specify"]


def test_canonical_helpers_exist():
    for name, path in CANONICAL.items():
        assert path.exists(), f"canonical {name} missing at {path}"


def test_no_stale_helper_copies():
    stale = []
    for skill in STALE_ARCHITECT_DIRS:
        for fname in STALE_ARCHITECT_FILES:
            sub = "powershell" if fname.endswith(".ps1") else "bash"
            p = ROOT / "skills/architect" / skill / "scripts" / sub / fname
            if p.exists():
                stale.append(str(p.relative_to(ROOT)))
    for skill in STALE_PRODUCT_DIRS:
        for fname, sub in (("pdr-lib.sh", "bash"), ("pdr-lib.ps1", "powershell")):
            p = ROOT / "skills/product" / skill / "scripts" / sub / fname
            if p.exists():
                stale.append(str(p.relative_to(ROOT)))
    assert not stale, f"stale helper copies reappeared: {stale}"


def test_borrower_source_lines_resolve_to_canonical():
    """Each borrower source line, resolved from its own dir, hits the canonical file."""
    for borrower, snippet in BASH_BORROWERS.items():
        content = borrower.read_text(encoding="utf-8")
        assert snippet in content, f"{borrower.name}: missing canonical reference"
        resolved = os.path.normpath(os.path.join(str(borrower.parent), snippet))
        expected = str(CANONICAL["pdr-lib.sh"])
        assert resolved == expected, f"{borrower.name}: resolves to {resolved}, want {expected}"


def test_borrower_refs_resolve_in_mirror_tree():
    """Same references must resolve under the installed flat mirror tree."""
    if not MIRROR.exists():
        pytest.skip("installed mirror absent — regenerate with adlc-cli")
    for borrower, snippet in BASH_BORROWERS.items():
        rel = borrower.relative_to(ROOT / "skills")
        # source skills/<group>/<skill>/... -> mirror .agents/skills/<skill>/...
        mirror_borrower = MIRROR / rel.parts[1] / Path(*rel.parts[2:])
        assert mirror_borrower.exists(), f"mirror missing borrower {mirror_borrower}"
        assert (MIRROR / "product-clarify/scripts/bash/pdr-lib.sh").exists(), \
            "mirror missing canonical pdr-lib.sh"
        resolved = os.path.normpath(os.path.join(str(mirror_borrower.parent), snippet))
        assert resolved == str(MIRROR / "product-clarify/scripts/bash/pdr-lib.sh"), \
            f"mirror resolve mismatch: {resolved}"


def test_skill_docs_point_at_canonical():
    for doc, canon in DOC_BORROWERS.items():
        content = doc.read_text(encoding="utf-8")
        assert canon in content, f"{doc.parent.name}/SKILL.md: missing canonical path"
    # borrower docs must not keep the bare per-skill-relative token
    for doc in [ROOT / "skills/architect/architect-analyze/SKILL.md",
                ROOT / "skills/architect/architect-implement/SKILL.md",
                ROOT / "skills/architect/architect-init/SKILL.md",
                ROOT / "skills/architect/architect-specify/SKILL.md"]:
        assert "`scripts/bash/setup-architect.sh`" not in doc.read_text(encoding="utf-8"), \
            f"{doc.parent.name}/SKILL.md: stale bare path"
