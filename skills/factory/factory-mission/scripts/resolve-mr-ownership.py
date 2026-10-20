#!/usr/bin/env python3
"""Resolve MR/PR milestone + assignee propagation (the MR-ownership decision).

The orchestrator opens (or reuses) a draft MR. This resolver decides what
ownership fields that MR should carry, so the decision is a deterministic
computation rather than an in-prompt judgement. The connector still performs
every tracker call; this only answers *what to set, what to skip, and what
to block on*.

Usage:
    resolve-mr-ownership.py <payload.json>
    ... | resolve-mr-ownership.py          # payload on stdin

Input (JSON):
    {
      "provider": "gitlab" | "github" | "jira" | "linear",
      "issue":  {"milestone_id": 7, "milestone": {"number": 3},
                  "assignees": ["alice", "bob"]},
      "mr":     {"milestone_id": null, "milestone": null,
                  "assignees": []},
      "initiator": "alice",        # the identity that triggered the run
      "runner":    "ci-bot",       # the runner's validated committer identity
      "denied_scope": null         # set when the connector pre-flight found a
                                   # missing read/write scope
    }

Output (JSON on stdout):
    {
      "action": "set" | "skip" | "block",
      "milestone": <value> | null,
      "milestone_field": "milestone_id" | "milestone" | null,
      "assignee": <login> | null,
      "assignee_field": "assignee_ids" | "assignees" | ... | null,
      "reason": "<human-readable, actionable>"
    }

Rules (the MR-ownership decision — all five user rulings are encoded here):

  * all providers    — the mapping lives in the provider adapter table below.
  * silent skip      — an Issue with no milestone produces no milestone work
                       and no error.
  * fallback chain   — assignee = initiator -> Issue assignees -> runner.
  * preserve-only    — a field is set only when the MR's field is empty.
  * block on error   — a missing scope blocks the run with an actionable
                       error that names the scope.
"""

import json
import sys

# Provider adapter (the MR-ownership decision §Decision Outcome step 2). A provider without a
# milestone concept gets None — a permanent no-op for that field, never an
# error (the MR-ownership decision "providers without a milestone concept are permanent no-ops").
PROVIDERS = {
    "gitlab": {"milestone_field": "milestone_id", "milestone_source": "milestone_id", "assignee_field": "assignee_ids"},
    "github": {"milestone_field": "milestone", "milestone_source": "milestone.number", "assignee_field": "assignees"},
    "jira": {"milestone_field": None, "milestone_source": None, "assignee_field": "assignee"},
    "linear": {"milestone_field": None, "milestone_source": None, "assignee_field": "assigneeId"},
}


def read_milestone(issue, source):
    """The Issue's milestone in the provider's own value space, or None."""
    if source is None:
        return None
    if source == "milestone.number":
        milestone = issue.get("milestone")
        if isinstance(milestone, dict):
            return milestone.get("number")
        return milestone
    value = issue.get(source)
    return value if value not in ("", None) else None


def resolve(payload):
    provider = str(payload.get("provider") or "").lower()
    adapter = PROVIDERS.get(provider)
    if adapter is None:
        return {
            "action": "block",
            "milestone": None,
            "milestone_field": None,
            "assignee": None,
            "assignee_field": None,
            "reason": f"unknown provider '{provider}' — expected one of {', '.join(sorted(PROVIDERS))}",
        }

    issue = payload.get("issue") or {}
    mr = payload.get("mr") or {}

    # (7) pre-flight scope check -> (6) block the run with an actionable error.
    denied = payload.get("denied_scope")
    if denied:
        return {
            "action": "block",
            "milestone": None,
            "milestone_field": None,
            "assignee": None,
            "assignee_field": None,
            "reason": (
                f"missing {denied} scope for {provider} — the run cannot read the Issue or write the "
                f"MR's ownership fields. Grant the scope and re-run; the factory never guesses a "
                f"milestone or an assignee it could not verify."
            ),
        }

    notes = []

    # (2) map the milestone through the provider adapter.
    milestone = None
    milestone_field = None
    if adapter["milestone_field"] is None:
        notes.append(f"{provider} has no milestone concept — milestone is a permanent no-op")
    else:
        value = read_milestone(issue, adapter["milestone_source"])
        if value is None:
            # (5) silent skip — no milestone on the Issue is not an error.
            notes.append("Issue has no milestone — skipped")
        elif not _mr_field_empty(mr, adapter["milestone_field"]):
            # (4) preserve-only — never overwrite a milestone a human set.
            notes.append(f"MR already has a {adapter['milestone_field']} — preserved")
        else:
            milestone = value
            milestone_field = adapter["milestone_field"]

    # (3) resolve the assignee through the fallback chain.
    assignee = None
    assignee_field = None
    if not _mr_field_empty(mr, adapter["assignee_field"]):
        notes.append(f"MR already has an {adapter['assignee_field']} — preserved")
    else:
        assignee = _first_candidate(
            payload.get("initiator"),
            issue.get("assignees"),
            payload.get("runner"),
        )
        if assignee is None:
            notes.append("no assignee candidate (no initiator, no Issue assignee, no runner identity) — skipped")
        else:
            assignee_field = adapter["assignee_field"]

    action = "set" if (milestone is not None or assignee is not None) else "skip"
    reason = "; ".join(notes) if notes else "milestone and assignee propagated"
    return {
        "action": action,
        "milestone": milestone,
        "milestone_field": milestone_field,
        "assignee": assignee,
        "assignee_field": assignee_field,
        "reason": reason,
    }


def _first_candidate(initiator, issue_assignees, runner):
    """initiator -> Issue assignees -> runner identity (the MR-ownership decision step 3)."""
    if initiator:
        return initiator
    if isinstance(issue_assignees, list):
        for candidate in issue_assignees:
            if candidate:
                return candidate
    if runner:
        return runner
    return None


def _mr_field_empty(mr, field):
    """True when the MR's field is unset — the preserve-only guard."""
    if field is None:
        return True
    value = mr.get(field)
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, str)):
        return len(value) == 0
    return False


def main(argv):
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.load(sys.stdin)
    print(json.dumps(resolve(payload), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
