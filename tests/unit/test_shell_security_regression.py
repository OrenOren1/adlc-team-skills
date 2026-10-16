"""Regression: shell scripts must not interpolate shell vars into python3 -c code
or build JSON by string concatenation (Socket/Snyk command-injection + JSON-injection).

RED test: fails on current tree (11 interpolation sites + manual JSON builders).
GREEN: passes after argv-passing + json.dumps fixes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

INTERP_RE = re.compile(r"python3\s+-c\s+\"[^\"]*with open\('[^']*\$", re.DOTALL)
UNESCAPED_JSON_RE = re.compile(r"printf\s+'\{.*%s|cat\s+<<EOF\s*\n\{.*\$", re.DOTALL)
EVAL_RE = re.compile(r'^[^#]*\beval\s+"\$\(', re.MULTILINE)


def _sh_files():
    return sorted((ROOT / "skills").rglob("*.sh"))


def test_no_python_c_interpolation():
    offenders = []
    for f in _sh_files():
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if INTERP_RE.search(content):
            offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, (
        "Shell-to-Python interpolation (Socket/Snyk command injection):\n"
        + "\n".join(offenders)
        + "\nFix: python3 -c '...sys.argv[1]...' \"$VAR\""
    )


def test_no_unescaped_json_builders():
    offenders = []
    for f in _sh_files():
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if UNESCAPED_JSON_RE.search(content):
            offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, (
        "Manual JSON string building (JSON injection / broken output):\n"
        + "\n".join(offenders)
        + "\nFix: python3 ... json.dumps via sys.argv or jq -n"
    )


def test_no_eval_of_function_output():
    offenders = []
    for f in _sh_files():
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if EVAL_RE.search(content):
            offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, (
        "eval $(...) executes function output (Socket command injection):\n"
        + "\n".join(offenders)
        + "\nFix: call function directly; it already sets globals"
    )
