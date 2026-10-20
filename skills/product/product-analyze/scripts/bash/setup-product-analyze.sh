#!/bin/bash
# product-analyze setup script
set -euo pipefail
JSON_MODE=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true ;; esac; done
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# shared layout constants (single definition in paths.sh).
_pd_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh"
elif [ -f "$_pd_dir/../../../workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../workspace/scripts/bash/paths.sh"
fi
PDR_DRAFTS_DIR="$REPO_ROOT/${ADLC_DRAFTS:-.adlc/drafts}/pdr"
PRD_FILE="$REPO_ROOT/${DOCS_ADLC_PRODUCT:-docs/adlc/product}/PRD.md"
PDR_COUNT=$(find "$PDR_DRAFTS_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l)
# dual-read: compiled PRD at docs/adlc/product/PRD.md, legacy repo-root
# PRD.md fallback (either counts as present).
PRD_EXISTS=false
if [ -f "$PRD_FILE" ] || [ -f "$REPO_ROOT/PRD.md" ]; then PRD_EXISTS=true; fi
if $JSON_MODE; then
  python3 - "$REPO_ROOT" "$PDR_DRAFTS_DIR" "$PRD_FILE" "$PDR_COUNT" "$PRD_EXISTS" <<'PY'
import json, sys
print(json.dumps({
  "REPO_ROOT": sys.argv[1],
  "PDR_DRAFTS_DIR": sys.argv[2],
  "PRD_FILE": sys.argv[3],
  "pdr_count": int(sys.argv[4]),
  "prd_exists": sys.argv[5] == "true"
}))
PY
else
  echo "[INFO] product-analyze setup"
  echo "  PDRs: $PDR_COUNT"
  echo "  PRD exists: $PRD_EXISTS"
fi
