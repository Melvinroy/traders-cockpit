param(
  [Parameter(Mandatory = $true)]
  [string]$SourceBranch,

  [ValidateSet("integration", "main")]
  [string]$Target = "integration"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")

$targetBranch = if ($Target -eq "integration") { "codex/integration-app" } else { "main" }

git -C $repoRoot fetch --all --prune
git -C $repoRoot checkout $targetBranch
git -C $repoRoot merge --no-ff $SourceBranch

Write-Host "Merged $SourceBranch into $targetBranch"
