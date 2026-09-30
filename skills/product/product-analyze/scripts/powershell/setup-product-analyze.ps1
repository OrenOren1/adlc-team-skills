# product-analyze setup script (PowerShell)
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
$PrdFile = Join-Path $RepoRoot "PRD.md"
$pdrCount = if (Test-Path $PdrDraftsDir) { (Get-ChildItem -Path $PdrDraftsDir -Filter 'PDR-*.md').Count } else { 0 }
$prdExists = Test-Path $PrdFile
if ($Json) {
  Write-Output (@{ REPO_ROOT=$RepoRoot; PDR_DRAFTS_DIR=$PdrDraftsDir; PRD_FILE=$PrdFile; pdr_count=$pdrCount; prd_exists=$prdExists } | ConvertTo-Json)
} else {
  Write-Output "[INFO] product-analyze setup"
  Write-Output "  PDRs: $pdrCount"
  Write-Output "  PRD exists: $prdExists"
}
