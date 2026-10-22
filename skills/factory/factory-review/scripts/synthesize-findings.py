#!/usr/bin/env python3
"""Deterministic synthesis of adversarial review findings.

Reads findings JSON (file arg or stdin) shaped like:
{"findings":[{"id":"F1","reports":["Auditor","Adversary"],
"validations":[],"challenges":[],"adds":[]}, ...]}
writes tags JSON to stdout. Deterministic: same input -> byte-identical output.
Counting rule: >=2 *distinct* reporters -> cross-validated; 1 report + >=1
validate from a *different* persona (no challenge) -> consensus; 1 report +
>=1 challenge -> disputed; else solo.
Round-2 `add` moves arrive as separate findings with the adder in `reports`
(e.g. {"id":"F1a","reports":["Adversary"],"validations":[],"challenges":[]});
the script never invents findings — every `add` is already a record.
"""
import json
import sys


def _personas(value):
    """Distinct reporter/validator names from a reports-like value.

    Non-list input (e.g. a bare string) yields an empty set so malformed
    records fall through to `solo` instead of being length-counted.
    """
    if not isinstance(value, list):
        return set()
    return {v for v in value if isinstance(v, str) and v}


def tag(f):
    reports = _personas(f.get("reports", []))
    validations = _personas(f.get("validations", []))
    challenges = f.get("challenges", []) or []
    if not isinstance(challenges, list):
        challenges = [challenges]
    if len(reports) >= 2:
        return "cross-validated"
    if len(reports) == 1 and challenges:
        return "disputed"
    if len(reports) == 1 and (validations - reports):
        return "consensus"
    return "solo"


def main(argv):
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        print("usage: synthesize-findings.py [findings.json]")
        return 0
    if len(argv) > 2:
        print("synthesize-findings: expected at most one findings JSON path",
              file=sys.stderr)
        return 2
    src = argv[1] if len(argv) > 1 else "-"
    try:
        if src != "-":
            with open(src, encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
        data = json.loads(raw)
    except FileNotFoundError:
        print(f"synthesize-findings: no such file: {src}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"synthesize-findings: invalid findings JSON: {exc}",
              file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"synthesize-findings: cannot read input: {exc}",
              file=sys.stderr)
        return 2
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        print("synthesize-findings: expected {\"findings\": [...]}",
              file=sys.stderr)
        return 2
    findings = data["findings"]
    if any(not isinstance(f, dict) for f in findings):
        print("synthesize-findings: every finding must be an object",
              file=sys.stderr)
        return 2
    tags = [{"id": f.get("id", ""), "tag": tag(f)} for f in findings]
    sys.stdout.write(json.dumps({"tags": tags}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
