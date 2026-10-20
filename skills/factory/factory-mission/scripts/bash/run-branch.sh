#!/usr/bin/env bash
# run-branch.sh — check out the intent run branch in the project root
# (ADR-431-amendment §1, adlc-workspace#26).
#
# With a factory run context (ADLC_RUN_ID, ADR-444): check out
#   factory/<repo>-<iid>   from ADLC_ISSUE_REF (<group>/<repo>#<iid>), or
#   factory/run-<run_id>   without an issue,
# reusing a local branch, or continuing from origin when only the remote has
# it. The branch is shared by both intent lanes and by re-dispatches of the
# same issue. Without ADLC_RUN_ID this is a no-op (interactive sessions never
# switch branches). Prints the branch name on stdout.
set -euo pipefail

die() { echo "run-branch: $*" >&2; exit 2; }

if [ -z "${ADLC_RUN_ID:-}" ]; then
  echo "run-branch: no run context (ADLC_RUN_ID unset) — skipped" >&2
  exit 0
fi
[[ "$ADLC_RUN_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "invalid ADLC_RUN_ID"

root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git work tree"
cd "$root"

if [ -n "${ADLC_ISSUE_REF:-}" ]; then
  # Never build a ref from anything but a plain <path>#<number>.
  case "$ADLC_ISSUE_REF" in *..*|/*|*//*) die "invalid ADLC_ISSUE_REF";; esac
  [[ "$ADLC_ISSUE_REF" =~ ^([A-Za-z0-9._-]+/)+([A-Za-z0-9_][A-Za-z0-9._-]*)#([0-9]+)$ ]] || die "invalid ADLC_ISSUE_REF"
  branch="factory/${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
else
  branch="factory/run-${ADLC_RUN_ID}"
fi
git check-ref-format "refs/heads/$branch" || die "invalid branch name: $branch"

if git show-ref --verify --quiet "refs/heads/$branch"; then
  git switch -q "$branch"
elif git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  git fetch -q origin "+refs/heads/$branch:refs/remotes/origin/$branch"
  git switch -q -c "$branch" --track "origin/$branch"
else
  git switch -q -c "$branch"
fi
echo "$branch"
