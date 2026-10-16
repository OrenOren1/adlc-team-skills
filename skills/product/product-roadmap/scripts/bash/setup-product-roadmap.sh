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
PDR_DRAFTS_DIR="$REPO_ROOT/${ADLC_DRAFTS:-.adlc/drafts}/pdr"
# ADR-401: canonical memory root is docs/adlc/memory; legacy .adlc/memory
# stays read-compatible — memory counts sum both roots (dual-read R8).
PDR_MEMORY_DIR="$REPO_ROOT/docs/adlc/memory/pdr"
LEGACY_PDR_MEMORY_DIR="$REPO_ROOT/.adlc/memory/pdr"
PRD_FILE="$REPO_ROOT/${DOCS_ADLC_PRODUCT:-docs/adlc/product}/PRD.md"
mkdir -p "$PDR_DRAFTS_DIR"
DRAFT_COUNT=$(find "$PDR_DRAFTS_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l)
MEM_COUNT=$(( $(find "$PDR_MEMORY_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l) + $(find "$LEGACY_PDR_MEMORY_DIR" -name 'PDR-*.md' 2>/dev/null | wc -l) ))
if $JSON_MODE; then
  python3 - "$REPO_ROOT" "$PDR_DRAFTS_DIR" "$PDR_MEMORY_DIR" "$PRD_FILE" "$DRAFT_COUNT" "$MEM_COUNT" <<'PY'
import json, sys
print(json.dumps({
  "REPO_ROOT": sys.argv[1],
  "PDR_DRAFTS_DIR": sys.argv[2],
  "PDR_MEMORY_DIR": sys.argv[3],
  "PRD_FILE": sys.argv[4],
  "draft_count": int(sys.argv[5]),
  "memory_count": int(sys.argv[6])
}))
PY
else
  echo "[INFO] product-roadmap setup"
  echo "  Draft PDRs: $DRAFT_COUNT"
  echo "  Memory PDRs: $MEM_COUNT"
fi
