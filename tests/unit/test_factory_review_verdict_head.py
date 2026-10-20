"""The factory-review verdict must name the head it certifies — and be checkable.

A verdict certifies exactly one head SHA. A fix push moves the head and
invalidates the verdict, so the review has to run again before
merge-readiness is claimed. The rule is stated in the skill; these tests pin
both halves of it:

  * the marker the skill tells the reviewer to post actually carries
    ``head=<sha>`` — without it the verdict certifies nothing, and
  * the checker that enforces it exists, behaves correctly, and is wired
    into CI.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
SKILL = ROOT / "skills/factory/factory-review"
SKILL_MD = SKILL / "SKILL.md"
LOOP_MD = SKILL / "references/review-loop.md"
CHECKER = SKILL / "scripts/check-verdict-head.sh"
WORKFLOW = ROOT / ".github/workflows/verdict-head.yml"

MARKER = "factory-review:step=review"


def run_checker(tmp_path, bodies, pr_head):
    """Run the checker over a fixture of comment bodies; return (rc, output)."""
    fixture = tmp_path / "verdicts.txt"
    fixture.write_text(bodies, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(CHECKER), "--verdicts", str(fixture), "--pr-head", pr_head],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout + proc.stderr


def verdict(head, extra=""):
    return (
        f"<!-- {MARKER} run=r1 iter=0 status=completed findings=1 "
        f"important=0 nits=1 {extra}head={head} -->\nA review comment.\n"
    )


def review_marker_templates(text):
    """Every review marker template in the text, joined across wrapped lines.

    The skill's diagram wraps the marker over two lines to fit the box, so
    the template has to be re-joined before it can be read as a marker.
    """
    joined = re.sub(r"\s*\n\s*", " ", text)
    return [m for m in re.findall(r"<!--.*?-->", joined) if MARKER in m]


# ── the live path: a mocked `gh` on PATH ───────────────────────────────────
#
# `fetch_bodies` is the only code that talks to GitHub, so it is the only part
# of the checker the offline fixtures cannot reach. The mock serves canned
# payloads and applies the `--jq` filter with jq — the same engine gh uses.

MOCK_GH = '''#!/usr/bin/env python3
"""A mock `gh` for the verdict-head checker: serves canned PR payloads."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def emulate(filt, data):
    """Fallback rendering of the record filters the checker uses."""
    key = "submitted_at" if "submitted_at" in filt else "created_at"
    out = []
    for item in data:
        ts = item.get(key) or item.get("created_at") or ""
        out.append("%%%s\\n%s\\n" % (ts, item.get("body") or ""))
    return "".join(out)


def main(argv):
    endpoint = None
    filt = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--jq":
            filt = argv[i + 1]
            i += 2
            continue
        if arg in ("api", "--paginate") or arg.startswith("-"):
            i += 1
            continue
        endpoint = arg
        i += 1

    if endpoint is None:
        print("mock gh: no endpoint", file=sys.stderr)
        return 1
    if endpoint.endswith("/comments"):
        kind = "comments"
    elif endpoint.endswith("/reviews"):
        kind = "reviews"
    else:
        print("mock gh: unexpected endpoint %s" % endpoint, file=sys.stderr)
        return 1

    if os.environ.get("MOCK_FAIL") == kind:
        print("gh: API rate limit exceeded for %s" % endpoint, file=sys.stderr)
        return 1

    payload = Path(os.environ["MOCK_" + kind.upper()]).read_text(encoding="utf-8")
    if not filt:
        sys.stdout.write(payload)
        return 0

    jq = shutil.which("jq")
    if jq:
        proc = subprocess.run(
            [jq, "-r", filt], input=payload, capture_output=True, text=True
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            return proc.returncode
        sys.stdout.write(proc.stdout)
        return 0

    sys.stdout.write(emulate(filt, json.loads(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def comment(ts, body):
    """An issue comment, as the comments API returns it."""
    return {"created_at": ts, "body": body}


def review(ts, body):
    """A review, as the reviews API returns it."""
    return {"submitted_at": ts, "body": body}


def run_checker_live(tmp_path, comments, reviews, pr_head, fail=None):
    """Run the checker against a mocked GitHub; return (rc, output)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    mock = bin_dir / "gh"
    mock.write_text(MOCK_GH, encoding="utf-8")
    mock.chmod(0o755)

    comments_file = tmp_path / "comments.json"
    comments_file.write_text(json.dumps(comments), encoding="utf-8")
    reviews_file = tmp_path / "reviews.json"
    reviews_file.write_text(json.dumps(reviews), encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["MOCK_COMMENTS"] = str(comments_file)
    env["MOCK_REVIEWS"] = str(reviews_file)
    if fail:
        env["MOCK_FAIL"] = fail

    proc = subprocess.run(
        [
            "bash",
            str(CHECKER),
            "--repo",
            "tikalk/adlc-team-skills",
            "--pr",
            "79",
            "--pr-head",
            pr_head,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


# ── the marker the skill tells the reviewer to post ────────────────────────

def test_skill_marker_template_carries_the_head():
    content = SKILL_MD.read_text(encoding="utf-8")
    templates = review_marker_templates(content)
    assert templates, "the skill must show the review marker template"
    for template in templates:
        assert "head=" in template, (
            "the review marker template must carry the head it certifies: "
            f"{template.strip()}"
        )


def test_review_loop_marker_template_carries_the_head():
    content = LOOP_MD.read_text(encoding="utf-8")
    templates = review_marker_templates(content)
    assert templates, "the review-loop reference must show the review marker"
    for template in templates:
        assert "head=" in template, (
            f"the review marker must carry the head it certifies: {template.strip()}"
        )


def test_skill_states_the_rule_and_names_the_checker():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Re-review after any fix push" in content, (
        "the skill must state the re-review-after-fix rule"
    )
    assert "head=<sha>" in content, "the skill must require the head in the marker"
    assert "check-verdict-head.sh" in content, (
        "the skill must name the checker that enforces the rule"
    )


# ── the checker ───────────────────────────────────────────────────────────

def test_checker_exists_and_is_executable():
    assert CHECKER.exists(), f"the verdict checker is missing at {CHECKER}"
    assert os.access(CHECKER, os.X_OK), "the checker must be executable"


def test_verdict_naming_the_current_head_passes(tmp_path):
    rc, out = run_checker(tmp_path, verdict("a" * 40), "a" * 40)
    assert rc == 0, out
    assert "OK" in out


def test_verdict_on_a_moved_head_fails(tmp_path):
    rc, out = run_checker(tmp_path, verdict("a" * 40), "b" * 40)
    assert rc == 1, out
    assert "FAIL" in out
    assert "a" * 40 in out and "b" * 40 in out, "the failure must name both heads"


def test_no_verdict_is_not_a_failure(tmp_path):
    rc, out = run_checker(tmp_path, "A human comment with no marker.\n", "a" * 40)
    assert rc == 0, out
    assert "nothing to verify" in out


def test_verdict_without_a_head_fails(tmp_path):
    """A verdict that names no head certifies nothing — it must not pass."""
    body = f"<!-- {MARKER} run=r1 iter=0 status=completed findings=0 important=0 nits=0 -->\n"
    rc, out = run_checker(tmp_path, body, "a" * 40)
    assert rc == 1, out
    assert "names no head" in out


def test_the_newest_verdict_wins(tmp_path):
    """An older verdict must not mask a newer one."""
    bodies = (
        verdict("a" * 40)
        + "%%%\n"
        + verdict("b" * 40)
    )
    rc, out = run_checker(tmp_path, bodies, "a" * 40)
    assert rc == 1, out
    assert "b" * 40 in out, "the newest verdict is the one that counts"

    rc, out = run_checker(tmp_path, bodies, "b" * 40)
    assert rc == 0, out


def test_non_verdict_markers_are_ignored(tmp_path):
    """A fix or converge marker is not a verdict — it must not be read as one."""
    bodies = (
        "<!-- factory-review:step=fix run=r1 iter=0 status=completed fixed=1 "
        "new_head_sha=" + "c" * 40 + " ci_status=pass -->\nA fix.\n"
        + "%%%\n"
        + verdict("a" * 40)
    )
    rc, out = run_checker(tmp_path, bodies, "a" * 40)
    assert rc == 0, out


def test_a_stale_fix_marker_does_not_satisfy_the_check(tmp_path):
    """Only the review verdict certifies; a fix marker never does."""
    bodies = (
        "<!-- factory-review:step=fix run=r1 iter=0 status=completed fixed=1 "
        "new_head_sha=" + "b" * 40 + " ci_status=pass -->\nA fix.\n"
    )
    rc, out = run_checker(tmp_path, bodies, "b" * 40)
    assert rc == 0, out
    assert "nothing to verify" in out


def test_missing_pr_head_is_a_usage_error(tmp_path):
    proc = subprocess.run(
        ["bash", str(CHECKER), "--verdicts", str(tmp_path / "nope.txt")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_a_trailing_flag_without_a_value_is_a_usage_error(tmp_path):
    """A flag with no value must not hang the parser."""
    for flag in ("--repo", "--pr", "--pr-head", "--verdicts"):
        proc = subprocess.run(
            ["bash", str(CHECKER), flag],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = proc.stdout + proc.stderr
        assert proc.returncode == 2, f"{flag} did not exit 2: {out}"
        assert "requires a value" in out, out


def test_a_head_that_is_not_a_full_sha_is_rejected(tmp_path):
    """A short SHA certifies nothing — it cannot be compared to a head."""
    rc, out = run_checker(tmp_path, verdict("abc1234"), "a" * 40)
    assert rc == 1, out
    assert "40-character SHA" in out


def test_a_missing_verdicts_file_is_an_error(tmp_path):
    """The offline path must not read a missing file as "no verdict"."""
    proc = subprocess.run(
        [
            "bash",
            str(CHECKER),
            "--verdicts",
            str(tmp_path / "nope.txt"),
            "--pr-head",
            "a" * 40,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "nothing to verify" not in proc.stdout + proc.stderr


# ── the live path (a mocked gh on PATH) ────────────────────────────────────

def test_the_live_path_picks_the_newest_verdict(tmp_path):
    """The newest verdict wins — an older one must not shadow it."""
    rc, out = run_checker_live(
        tmp_path,
        comments=[
            comment("2026-10-20T10:00:00Z", "A human note: we now add `head=<sha>` to the marker."),
            comment("2026-10-20T10:30:00Z", verdict("a" * 40)),
            comment("2026-10-20T11:40:45Z", verdict("b" * 40)),
        ],
        reviews=[],
        pr_head="b" * 40,
    )
    assert rc == 0, out
    assert "OK" in out


def test_the_live_path_reports_a_stale_verdict(tmp_path):
    rc, out = run_checker_live(
        tmp_path,
        comments=[comment("2026-10-20T11:40:45Z", verdict("a" * 40))],
        reviews=[],
        pr_head="b" * 40,
    )
    assert rc == 1, out
    assert "FAIL" in out
    assert "a" * 40 in out and "b" * 40 in out, "the failure must name both heads"


def test_a_review_body_newer_than_an_issue_comment_wins(tmp_path):
    """A verdict posted as a review is newer than one in the comment thread."""
    rc, out = run_checker_live(
        tmp_path,
        comments=[comment("2026-10-20T11:40:45Z", verdict("a" * 40))],
        reviews=[review("2026-10-20T12:00:00Z", verdict("b" * 40))],
        pr_head="b" * 40,
    )
    assert rc == 0, out


def test_prose_that_mentions_head_does_not_hijack_the_parse(tmp_path):
    """Only a head named INSIDE the marker counts."""
    rc, out = run_checker_live(
        tmp_path,
        comments=[
            comment(
                "2026-10-20T10:00:00Z",
                "We now write `head=<sha>` into the marker, so the check can read it back.",
            ),
            comment("2026-10-20T11:40:45Z", verdict("b" * 40)),
        ],
        reviews=[],
        pr_head="b" * 40,
    )
    assert rc == 0, out


def test_a_failed_comments_call_fails_closed(tmp_path):
    """A transient API error must never read as "there is no verdict"."""
    rc, out = run_checker_live(
        tmp_path,
        comments=[comment("2026-10-20T11:40:45Z", verdict("b" * 40))],
        reviews=[],
        pr_head="b" * 40,
        fail="comments",
    )
    assert rc == 2, out
    assert "could not read" in out
    assert "nothing to verify" not in out


def test_a_failed_reviews_call_fails_closed(tmp_path):
    rc, out = run_checker_live(
        tmp_path,
        comments=[comment("2026-10-20T11:40:45Z", verdict("b" * 40))],
        reviews=[],
        pr_head="b" * 40,
        fail="reviews",
    )
    assert rc == 2, out
    assert "could not read" in out


# ── CI wiring ─────────────────────────────────────────────────────────────

def test_ci_workflow_runs_the_checker():
    assert WORKFLOW.exists(), f"the CI workflow is missing at {WORKFLOW}"
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "check-verdict-head.sh" in content, "the workflow must run the checker"
    assert "pull_request" in content, "the workflow must run on pull requests"
    assert "synchronize" in content, (
        "the workflow must re-run when the head moves — that is the whole point"
    )
    assert "pull-requests: read" in content, "the workflow must stay read-only"


def test_the_workflow_re_runs_when_the_verdict_lands():
    """The verdict is posted as an issue comment — the check must hear it."""
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "issue_comment" in content, (
        "the verdict is posted with `gh pr comment`, so the workflow must "
        "listen for issue_comment or it can never turn green after a fix"
    )
    assert "github.event.pull_request.number || github.event.issue.number" in content, (
        "the PR number must be read from the payload of every trigger — a "
        "pull_request_review payload carries no top-level number"
    )
    assert ".head.sha" in content and "pulls/" in content, (
        "an issue_comment payload carries no head SHA, so the head must be "
        "resolved from the API when the event does not carry one"
    )


def test_the_workflow_stays_read_only():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in content, (
        "pull_request_target runs with write access to the base branch"
    )
    for scope in ("contents: read", "issues: read", "pull-requests: read"):
        assert scope in content, f"the workflow must keep `{scope}`"
