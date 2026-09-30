#!/bin/bash
# product-specify setup script
set -euo pipefail

JSON_MODE=false
for arg in "$@"; do
  case "$arg" in --json) JSON_MODE=true ;; esac
done

source "$(dirname "${BASH_SOURCE[0]}")/../../../product-clarify/scripts/bash/pdr-lib.sh" 2>/dev/null || true
# Fail fast when the canonical helper is absent (selective install without
# product-clarify) instead of dying later on a missing function.
command -v generate_pdr_index >/dev/null 2>&1 || { echo "ERROR: pdr-lib.sh not loaded — install the product-clarify skill: adlc-cli skills add tikalk/adlc-team-skills --skill product-clarify" >&2; return 1 2>/dev/null || exit 1; }

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
PRD_FILE="$REPO_ROOT/${DOCS_ADLC_PRODUCT:-docs/adlc/product}/PRD.md"

mkdir -p "$PDR_DRAFTS_DIR"

next_pdr_number() {
  local max=0
  if [[ -d "$PDR_DRAFTS_DIR" ]]; then
    for f in "$PDR_DRAFTS_DIR"/PDR-*.md; do
      if [[ -f "$f" ]]; then
        local num; num=$(basename "$f" | sed 's/PDR-//' | sed 's/\.md//')
        if [[ "$num" =~ ^[0-9]+$ ]]; then ((10#$num > max)) && max=$((10#$num)); fi
      fi
    done
  fi
  printf '%03d' $((max + 1))
}

NEXT_PDR=$(next_pdr_number)
PDR_COUNT=$(find "$PDR_DRAFTS_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l)

if $JSON_MODE; then
  cat <<EOF
{"REPO_ROOT":"$REPO_ROOT","PDR_DRAFTS_DIR":"$PDR_DRAFTS_DIR","PRD_FILE":"$PRD_FILE","next_pdr":"$NEXT_PDR","pdr_count":$PDR_COUNT}
EOF
else
  echo "[INFO] product-specify setup"
  echo "  REPO_ROOT: $REPO_ROOT"
  echo "  PDR_DRAFTS_DIR: $PDR_DRAFTS_DIR"
  echo "  Next PDR: PDR-$NEXT_PDR"
  echo "  Existing PDRs: $PDR_COUNT"
fi
