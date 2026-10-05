#!/bin/bash
# product-clarify setup script
set -euo pipefail
JSON_MODE=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true ;; esac; done

# Source pdr-lib.sh for _get_project_root (walks up to find .adlc, not just .git)
source "$(dirname "${BASH_SOURCE[0]}")/pdr-lib.sh" 2>/dev/null || true

# ADR-401 shared layout constants (single definition in paths.sh; pdr-lib.sh
# sources it too — this block keeps the script correct standalone).
_pd_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh"
elif [ -f "$_pd_dir/../../../workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../workspace/scripts/bash/paths.sh"
fi
REPO_ROOT="${REPO_ROOT:-$(_get_project_root)}"
PDR_DRAFTS_DIR="$REPO_ROOT/${ADLC_DRAFTS:-.adlc/drafts}/pdr"
# ADR-401: canonical PDR memory root (legacy .adlc/memory stays read-compatible).
PDR_MEMORY_DIR="$REPO_ROOT/docs/adlc/memory/pdr"
PRD_FILE="$REPO_ROOT/${DOCS_ADLC_PRODUCT:-docs/adlc/product}/PRD.md"
mkdir -p "$PDR_DRAFTS_DIR"
PDR_COUNT=$(find "$PDR_DRAFTS_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l)
ACCEPTED_COUNT=0
if [[ "$PDR_COUNT" -gt 0 ]]; then
  ACCEPTED_COUNT=$(count_pdr_accepted "$PDR_DRAFTS_DIR" 2>/dev/null || grep -lE '^#+\s*Status' "$PDR_DRAFTS_DIR"/PDR-*.md 2>/dev/null | xargs -I{} grep -l '^\*\*Accepted\*\*' {} 2>/dev/null | wc -l)
fi
if $JSON_MODE; then
  cat <<EOF
{"REPO_ROOT":"$REPO_ROOT","PDR_DRAFTS_DIR":"$PDR_DRAFTS_DIR","PDR_MEMORY_DIR":"$PDR_MEMORY_DIR","PRD_FILE":"$PRD_FILE","pdr_count":$PDR_COUNT,"accepted_count":$ACCEPTED_COUNT}
EOF
else
  echo "[INFO] product-clarify setup"
  echo "  PDRs found: $PDR_COUNT"
  echo "  Accepted: $ACCEPTED_COUNT"
fi
