#!/usr/bin/env bash
# Verify that the latest factory-review verdict names the current PR head.
#
# A factory-review verdict certifies exactly ONE head SHA — the one carried in
# its `head=<sha>` marker. Any push after the verdict (a fix, a rebase, a
# force-push) moves the head and invalidates it, so the review must run again
# on the new head before merge-readiness is claimed.
#
# The skill states that rule; this script makes it mechanical: it reads the
# PR's comments and review bodies, finds the latest factory-review review
# verdict, and compares the head it names with the head being merged.
#
# Usage:
#   check-verdict-head.sh --repo <owner/repo> --pr <number> --pr-head <sha>
#   check-verdict-head.sh --verdicts <file> --pr-head <sha>      # offline
#
# Exit codes:
#   0 = no factory-review verdict, or the verdict names the current head
#   1 = the verdict is stale or unbound — the review must be re-run on this head
#   2 = usage or infrastructure error (bad arguments, unreadable comments)
#
# The head is read from INSIDE the `<!-- factory-review:step=review … -->`
# marker only: prose that merely mentions `head=<sha>` — or a verdict that
# quotes an older verdict — cannot hijack the parse. The value must be a full
# 40-character SHA.
#
# Comments and review bodies are read as RECORDS. In the live path each
# record is introduced by a `%%%<timestamp>` line (the comment's created_at or
# the review's submitted_at), so the newest verdict wins even when it was
# posted as a review body while an older verdict sits in the comment thread.
# The --verdicts file uses the same `%%%` separator without a timestamp; there
# the last record is the newest.

set -u

REPO=""
PR=""
PR_HEAD=""
VERDICTS_FILE=""

# The marker that carries a review verdict.
MARKER='factory-review:step=review'

usage_error() {
    echo "check-verdict-head: $*" >&2
    exit 2
}

# A flag must be followed by a value. Without this check, `shift 2` on a
# trailing flag fails without shifting and the parser loops forever.
require_value() {
    if [ "$2" = "" ]; then
        usage_error "$1 requires a value"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo)     require_value "$1" "${2:-}"; REPO="$2"; shift 2 ;;
        --pr)       require_value "$1" "${2:-}"; PR="$2"; shift 2 ;;
        --pr-head)  require_value "$1" "${2:-}"; PR_HEAD="$2"; shift 2 ;;
        --verdicts) require_value "$1" "${2:-}"; VERDICTS_FILE="$2"; shift 2 ;;
        --help|-h)  awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"
                    exit 0 ;;
        *)          usage_error "unknown argument '$1'" ;;
    esac
done

if [ -z "$PR_HEAD" ]; then
    usage_error "--pr-head <sha> is required"
fi

# Run one `gh api` call and print the records it yields. Fails closed: a
# failed call is an infrastructure error, never "there is no verdict".
gh_records() {
    _endpoint="$1"
    _filter="$2"
    _label="$3"
    _err=$(mktemp)
    _out=$(gh api "$_endpoint" --paginate --jq "$_filter" 2>"$_err")
    _rc=$?
    if [ "$_rc" -ne 0 ]; then
        echo "check-verdict-head: could not read $_label (gh api exited $_rc):" >&2
        sed 's/^/  /' "$_err" >&2
        rm -f "$_err"
        exit 2
    fi
    rm -f "$_err"
    printf '%s\n' "$_out"
}

fetch_bodies() {
    if [ -n "$VERDICTS_FILE" ]; then
        if [ ! -f "$VERDICTS_FILE" ]; then
            echo "check-verdict-head: could not read the verdicts file '$VERDICTS_FILE'" >&2
            exit 2
        fi
        cat "$VERDICTS_FILE"
        return 0
    fi
    if ! command -v gh >/dev/null 2>&1; then
        echo "check-verdict-head: gh is not available and --verdicts was not given" >&2
        exit 2
    fi
    if [ -z "$REPO" ] || [ -z "$PR" ]; then
        missing=""
        [ -z "$REPO" ] && missing="--repo"
        [ -z "$PR" ] && missing="${missing:+$missing }--pr"
        echo "check-verdict-head: $missing required without --verdicts" >&2
        exit 2
    fi
    # Issue comments and review bodies both carry the marker; inline review
    # comments have no body, so the review body is what matters. Each record
    # is introduced by "%%%<timestamp>" so the newest record wins no matter
    # which endpoint it came from.
    gh_records "repos/$REPO/issues/$PR/comments" \
        '.[] | "%%%" + (.created_at // "") + "\n" + (.body // "") + "\n"' \
        "the PR's issue comments"
    gh_records "repos/$REPO/pulls/$PR/reviews" \
        '.[] | "%%%" + (.submitted_at // .created_at // "") + "\n" + (.body // "") + "\n"' \
        "the PR's review bodies"
}

# The head named by the latest review verdict.
#
# Prints the SHA the newest verdict names, or nothing when the PR carries no
# factory-review verdict at all. Prints UNBOUND when a verdict exists but its
# marker names no head, and MALFORMED when the marker names something that is
# not a full 40-character SHA.
latest_verdict_head() {
    awk -v marker="$MARKER" '
        function is_sha(s) {
            return (length(s) == 40 && s ~ /^[0-9a-fA-F]+$/)
        }
        # The head= value carried by one marker line: the value itself when it
        # is a full SHA, "BAD" when the key is there but the value is not, and
        # "" when the line carries no head= key at all. Only the text from the
        # marker up to the closing "-->" of the marker is considered.
        function head_of(line,   m, region, e, n, tok, i, val) {
            m = index(line, marker)
            if (m == 0) return ""
            region = substr(line, m)
            e = index(region, "-->")
            if (e > 0) region = substr(region, 1, e - 1)
            n = split(region, tok, /[ \t]+/)
            val = ""
            for (i = 1; i <= n; i++) {
                if (substr(tok[i], 1, 5) == "head=") {
                    val = substr(tok[i], 6)
                    break
                }
            }
            if (val == "") return ""
            if (!is_sha(val)) return "BAD"
            return val
        }
        {
            if (substr($0, 1, 3) == "%%%") {
                # The separator introduces the record that follows it, so the
                # timestamp it carries belongs to that record, not to the one
                # that just ended.
                rec[++n] = cur
                ts[n] = pending_ts
                cur = ""
                started = 0
                pending_ts = substr($0, 4)
                next
            }
            if (!started) { cur = $0; started = 1 }
            else { cur = cur "\n" $0 }
        }
        END {
            rec[++n] = cur
            ts[n] = pending_ts
            best = 0
            best_ts = ""
            best_head = ""
            best_bad = 0
            for (i = 1; i <= n; i++) {
                head = ""
                bad = 0
                found = 0
                nl = split(rec[i], lines, "\n")
                for (l = 1; l <= nl; l++) {
                    if (index(lines[l], marker) == 0) continue
                    found = 1
                    h = head_of(lines[l])
                    if (h == "BAD") { bad = 1; continue }
                    if (h != "") { head = h; break }
                }
                if (!found) continue
                if (best == 0) {
                    best = i; best_ts = ts[i]; best_head = head; best_bad = bad
                    continue
                }
                if (ts[i] != best_ts) {
                    # A record without a timestamp cannot beat a timestamped
                    # one; otherwise the newer timestamp wins.
                    if (ts[i] == "") continue
                    if (best_ts == "" || ts[i] > best_ts) {
                        best = i; best_ts = ts[i]; best_head = head; best_bad = bad
                    }
                    continue
                }
                # Same timestamp (or neither record has one): the later
                # record is the newer one.
                best = i; best_head = head; best_bad = bad
            }
            if (best == 0) exit 0
            if (best_head != "") { print best_head; exit 0 }
            if (best_bad) { print "MALFORMED"; exit 0 }
            print "UNBOUND"
        }
    '
}

BODIES=$(fetch_bodies) || exit 2

if ! VERDICT_HEAD=$(printf '%s\n' "$BODIES" | latest_verdict_head); then
    echo "check-verdict-head: could not parse the PR's comments (the parser failed)" >&2
    exit 2
fi

if [ -z "$VERDICT_HEAD" ]; then
    echo "check-verdict-head: OK — no factory-review verdict on this PR; nothing to verify."
    exit 0
fi

if [ "$VERDICT_HEAD" = "UNBOUND" ]; then
    echo "check-verdict-head: FAIL — a factory-review verdict exists but names no head."
    echo "  A verdict that names no head certifies nothing: it cannot be checked"
    echo "  against a head, so it cannot support a merge-ready claim."
    echo "  Re-run the review on the current head so the marker names it."
    exit 1
fi

if [ "$VERDICT_HEAD" = "MALFORMED" ]; then
    echo "check-verdict-head: FAIL — the verdict's head= value is not a full 40-character SHA."
    echo "  A verdict that names no usable head certifies nothing: it cannot be checked"
    echo "  against a head, so it cannot support a merge-ready claim."
    echo "  Re-run the review on the current head so the marker names it."
    exit 1
fi

verdict_head=$(printf '%s' "$VERDICT_HEAD" | tr '[:upper:]' '[:lower:]')
pr_head=$(printf '%s' "$PR_HEAD" | tr '[:upper:]' '[:lower:]')
if [ "$verdict_head" = "$pr_head" ]; then
    echo "check-verdict-head: OK — the verdict names the current head ($PR_HEAD)."
    exit 0
fi

echo "check-verdict-head: FAIL — the verdict names $VERDICT_HEAD but the head is $PR_HEAD."
echo "  A fix push invalidates the verdict: re-run the review passes on the current"
echo "  head and post the updated verdict naming $PR_HEAD before claiming merge-readiness."
exit 1
