#!/bin/bash
# product-roadmap setup script
set -euo pipefail
JSON_MODE=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true ;; esac; done
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# ADR-401 shared layout constants (single definition in paths.sh).
_pd_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../../team/workspace/scripts/bash/paths.sh"
elif [ -f "$_pd_dir/../../../workspace/scripts/bash/paths.sh" ]; then
  # shellcheck disable=SC1091
  . "$_pd_dir/../../../workspace/scripts/bash/paths.sh"
fi
PDR_DRAFTS_DIR="$REPO_ROOT/.adlc/drafts/pdr"
# ADR-401: canonical memory root is docs/adlc/memory; legacy .adlc/memory
# stays read-compatible — memory counts sum both roots (dual-read R8).
PDR_MEMORY_DIR="$REPO_ROOT/docs/adlc/memory/pdr"
LEGACY_PDR_MEMORY_DIR="$REPO_ROOT/.adlc/memory/pdr"
PRD_FILE="$REPO_ROOT/docs/adlc/product/PRD.md"
mkdir -p "$PDR_DRAFTS_DIR"
DRAFT_COUNT=$(find "$PDR_DRAFTS_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l)
MEM_COUNT=$(( $(find "$PDR_MEMORY_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l) + $(find "$LEGACY_PDR_MEMORY_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l) ))
if $JSON_MODE; then
  cat <<EOF
{"REPO_ROOT":"$REPO_ROOT","PDR_DRAFTS_DIR":"$PDR_DRAFTS_DIR","PDR_MEMORY_DIR":"$PDR_MEMORY_DIR","PRD_FILE":"$PRD_FILE","draft_count":$DRAFT_COUNT,"memory_count":$MEM_COUNT}
EOF
else
  echo "[INFO] product-roadmap setup"
  echo "  Draft PDRs: $DRAFT_COUNT"
  echo "  Memory PDRs: $MEM_COUNT"
fi
