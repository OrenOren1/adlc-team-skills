#!/usr/bin/env python3
"""Deterministic synthesis of adversarial review findings.

Reads findings JSON (file arg or stdin) shaped like:
{"findings":[{"id":"F1","reports":["Auditor","Adversary"],
"validations":[],"challenges":[],"adds":[]}, ...]}
writes tags JSON to stdout. Deterministic: same input -> byte-identical output.
Counting rule: >=2 reporters -> cross-validated; 1 report + >=1 validate
(no challenge) -> consensus; 1 report + >=1 challenge -> disputed; else solo.
Round-2 `add` moves arrive as separate findings with the adder in `reports`
(e.g. {"id":"F1a","reports":["Adversary"],"validations":[],"challenges":[]});
the script never invents findings — every `add` is already a record.
"""
import json
import sys


def tag(f):
    reports = f.get("reports", []) or []
    validations = f.get("validations", []) or []
    challenges = f.get("challenges", []) or []
    if len(reports) >= 2:
        return "cross-validated"
    if len(reports) == 1 and challenges:
        return "disputed"
    if len(reports) == 1 and validations:
        return "consensus"
    return "solo"


def main(argv):
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        print("usage: synthesize-findings.py [findings.json]")
        return 0
    src = argv[1] if len(argv) > 1 else "-"
    raw = open(src, encoding="utf-8").read() if src != "-" else sys.stdin.read()
    data = json.loads(raw)
    findings = data.get("findings", [])
    tags = [{"id": f.get("id", ""), "tag": tag(f)} for f in findings]
    sys.stdout.write(json.dumps({"tags": tags}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
