# product-roadmap setup script (PowerShell)
param([switch]$Json)
$ErrorActionPreference = "Stop"

# ADR-401 shared layout constants (single definition in paths.ps1).
$AdlcPathsPs1 = "$PSScriptRoot/../../../../team/workspace/scripts/powershell/paths.ps1"
if (-not (Test-Path $AdlcPathsPs1)) {
    $AdlcPathsPs1 = "$PSScriptRoot/../../../workspace/scripts/powershell/paths.ps1"
}
if (Test-Path $AdlcPathsPs1) { . $AdlcPathsPs1 }
$RepoRoot = $(git rev-parse --show-toplevel 2>$null); if (-not $RepoRoot) { $RepoRoot = Get-Location }
$PdrDraftsDir = Join-Path $RepoRoot ".adlc/drafts/pdr"
# ADR-401: canonical memory root is docs/adlc/memory; legacy .adlc/memory
# stays read-compatible — memory counts sum both roots (dual-read R8).
$PdrMemoryDir = Join-Path $RepoRoot "docs/adlc/memory/pdr"
$LegacyPdrMemoryDir = Join-Path $RepoRoot ".adlc/memory/pdr"
$PrdFile = Join-Path $RepoRoot "docs/adlc/product/PRD.md"
New-Item -ItemType Directory -Force -Path $PdrDraftsDir | Out-Null
$draftCount = if (Test-Path $PdrDraftsDir) { (Get-ChildItem -Path $PdrDraftsDir -Filter 'PDR-*.md').Count } else { 0 }
$memCount = ( @(Get-ChildItem -Path $PdrMemoryDir -Filter 'PDR-*.md' -ErrorAction SilentlyContinue).Count + @(Get-ChildItem -Path $LegacyPdrMemoryDir -Filter 'PDR-*.md' -ErrorAction SilentlyContinue).Count )
if ($Json) {
  Write-Output (@{ REPO_ROOT=$RepoRoot; PDR_DRAFTS_DIR=$PdrDraftsDir; PDR_MEMORY_DIR=$PdrMemoryDir; PRD_FILE=$PrdFile; draft_count=$draftCount; memory_count=$memCount } | ConvertTo-Json)
} else {
  Write-Output "[INFO] product-roadmap setup"
  Write-Output "  Draft PDRs: $draftCount"
  Write-Output "  Memory PDRs: $memCount"
}
