#!/usr/bin/env bash
# open-mr.sh — push the intent run branch and open (or reuse) its one draft MR
# (ADR-431-amendment §3, ADR-432, ADR-444; adlc-workspace#26).
#
# With a factory run context (ADLC_RUN_ID): pushes ONLY the current run branch
# (factory/*), finds an open MR/PR for it or creates one draft (squash off; the
# description states the merge-commit rule, ADR-431 §5), with the issue's
# milestone and assignees (ADR-432 chain: issue assignees, else the runner's
# own account), and merges {"mr_url": ...} into ADLC_STEP_OUTPUT. Titles are
# built from repo, iid and run id only — never issue text. A tracker refusal
# (e.g. missing scope) blocks: non-zero exit, nothing written. Without
# ADLC_RUN_ID this is a no-op. Prints the MR URL.
set -euo pipefail

die() { echo "open-mr: $*" >&2; exit 2; }
json() { node -e "$1" "${@:2}"; }

if [ -z "${ADLC_RUN_ID:-}" ]; then
  echo "open-mr: no run context (ADLC_RUN_ID unset) — skipped" >&2
  exit 0
fi
root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git work tree"
cd "$root"
branch="$(git branch --show-current)"
case "$branch" in factory/*) ;; *) die "not on a run branch (factory/*): '$branch'" ;; esac

origin="$(git config --get remote.origin.url)" || die "no origin remote"
read -r host project < <(json '
  const u = process.argv[1];
  let m = u.match(/^https:\/\/([^/@]+)\/(.+?)(?:\.git)?\/?$/) || u.match(/^(?:ssh:\/\/)?[^@]+@([^:/]+)[:/](.+?)(?:\.git)?$/);
  if (!m) process.exit(3);
  console.log(m[1] + " " + m[2]);
' "$origin") || die "cannot parse origin URL"
repo="${project##*/}"

issue_project="" iid=""
if [ -n "${ADLC_ISSUE_REF:-}" ]; then
  [[ "$ADLC_ISSUE_REF" =~ ^(([A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+)#([0-9]+)$ ]] || die "invalid ADLC_ISSUE_REF"
  issue_project="${BASH_REMATCH[1]}"; iid="${BASH_REMATCH[3]}"
  title="Draft: factory: ${issue_project##*/}#${iid} records (run ${ADLC_RUN_ID})"
else
  title="Draft: factory: run ${ADLC_RUN_ID} records"
fi
description="Factory intent run \`${ADLC_RUN_ID}\`${iid:+ for ${issue_project}#${iid}}. Merge with a merge commit, no squash (ADR-431 §5) — approved step SHAs must stay reachable."

provider="${ISSUE_PROVIDER:-gitlab}"
case "$provider" in
  gitlab)
    [ -n "${GITLAB_HOST:-}" ] || die "GITLAB_HOST is not set (the token is never sent to a guessed host)"
    want="${GITLAB_HOST#https://}"; want="${want%/}"
    [ "$host" = "$want" ] || die "origin host $host is not GITLAB_HOST ($want)"
    ;;
  github) [ "$host" = "github.com" ] || die "origin host $host is not github.com" ;;
  *) die "unsupported ISSUE_PROVIDER: $provider" ;;
esac

git push -q -u origin "refs/heads/$branch:refs/heads/$branch" || die "push of $branch failed"

enc() { json 'console.log(encodeURIComponent(process.argv[1]))' "$1"; }
url=""
if [ "$provider" = gitlab ]; then
  api() { glab api --hostname "$host" "$@"; }
  p="$(enc "$project")"
  existing="$(api "projects/$p/merge_requests?source_branch=$(enc "$branch")&state=opened")" || die "cannot list merge requests"
  url="$(json 'const a = JSON.parse(process.argv[1] || "[]"); console.log(Array.isArray(a) && a[0] && a[0].web_url || "")' "$existing")"
  if [ -z "$url" ]; then
    target="$(api "projects/$p" | json 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).default_branch||"main"))')"
    args=(-X POST "projects/$p/merge_requests" -f "source_branch=$branch" -f "target_branch=$target" -f "title=$title" -f "squash=false" -f "description=$description")
    assignees=""
    if [ -n "$iid" ]; then
      issue="$(api "projects/$(enc "$issue_project")/issues/$iid")" || die "cannot read issue $issue_project#$iid"
      milestone="$(json 'const i = JSON.parse(process.argv[1]); console.log(i.milestone && i.milestone.id || "")' "$issue")"
      [ -z "$milestone" ] || args+=(-f "milestone_id=$milestone")
      assignees="$(json 'const i = JSON.parse(process.argv[1]); console.log((i.assignees || []).map(a => a.id).join(" "))' "$issue")"
    fi
    if [ -z "$assignees" ]; then
      assignees="$(api user | json 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).id||""))')"
    fi
    for a in $assignees; do args+=(-f "assignee_ids[]=$a"); done
    created="$(api "${args[@]}")" || die "the tracker refused to create the merge request (missing scope?)"
    url="$(json 'console.log(JSON.parse(process.argv[1]).web_url || "")' "$created")"
  fi
else
  api() { gh api --hostname github.com "$@"; }
  owner="${project%%/*}"
  existing="$(api "repos/$project/pulls?head=$owner:$branch&state=open")" || die "cannot list pull requests"
  url="$(json 'const a = JSON.parse(process.argv[1] || "[]"); console.log(Array.isArray(a) && a[0] && a[0].html_url || "")' "$existing")"
  if [ -z "$url" ]; then
    target="$(api "repos/$project" | json 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).default_branch||"main"))')"
    created="$(api -X POST "repos/$project/pulls" -f "head=$branch" -f "base=$target" -f "title=${title#Draft: }" -f "body=$description" -F draft=true)" || die "the tracker refused to create the pull request (missing scope?)"
    url="$(json 'console.log(JSON.parse(process.argv[1]).html_url || "")' "$created")"
    number="$(json 'console.log(JSON.parse(process.argv[1]).number || "")' "$created")"
    if [ -n "$iid" ] && [ -n "$number" ]; then
      issue="$(api "repos/$issue_project/issues/$iid")" || die "cannot read issue $issue_project#$iid"
      milestone="$(json 'const i = JSON.parse(process.argv[1]); console.log(i.milestone && i.milestone.number || "")' "$issue")"
      [ -z "$milestone" ] || api -X PATCH "repos/$project/issues/$number" -F "milestone=$milestone" >/dev/null || die "cannot set milestone"
      logins="$(json 'const i = JSON.parse(process.argv[1]); console.log((i.assignees || []).map(a => a.login).join(" "))' "$issue")"
      [ -n "$logins" ] || logins="$(api user | json 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).login||""))')"
      for l in $logins; do api -X POST "repos/$project/issues/$number/assignees" -f "assignees[]=$l" >/dev/null || die "cannot set assignee"; done
    fi
  fi
fi
[ -n "$url" ] || die "no MR URL returned"

if [ -n "${ADLC_STEP_OUTPUT:-}" ]; then
  mkdir -p "$(dirname "$ADLC_STEP_OUTPUT")"
  json '
    const fs = require("node:fs"); const [file, url] = process.argv.slice(1);
    let o = {}; try { const v = JSON.parse(fs.readFileSync(file, "utf-8")); if (v && typeof v === "object" && !Array.isArray(v)) o = v; } catch {}
    o.mr_url = url; fs.writeFileSync(file, JSON.stringify(o));
  ' "$ADLC_STEP_OUTPUT" "$url"
fi
echo "$url"
