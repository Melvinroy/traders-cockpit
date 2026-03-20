param(
  [Parameter(Mandatory = $true)]
  [string]$Slug,

  [ValidateSet("feature", "bugfix", "refactor")]
  [string]$Type = "feature",

  [string]$Title = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$dateStamp = Get-Date -Format "yyyy-MM-dd"
$safeSlug = ($Slug.Trim().ToLower() -replace "[^a-z0-9\\-]", "-") -replace "-+", "-"
$issueDir = Join-Path $repoRoot "docs\\issues"
$templatePath = Join-Path $issueDir "TEMPLATE.md"
$issuePath = Join-Path $issueDir "$dateStamp-$safeSlug.md"
$branchName = "codex/$Type-$safeSlug"

if (-not (Test-Path $issuePath)) {
  $content = Get-Content $templatePath -Raw
  if ($Title.Trim()) {
    $content = $content -replace "# Title", "# $Title"
  }
  Set-Content -Path $issuePath -Value $content -Encoding UTF8
  Write-Host "Created local issue note: $issuePath"
}

$insideGit = ((git -C $repoRoot rev-parse --is-inside-work-tree) 2>$null).Trim() -eq "true"
if (-not $insideGit) {
  throw "Not inside a git repository."
}

$integrationExists = ((git -C $repoRoot branch --list "codex/integration-app") | Out-String).Trim()
if (-not $integrationExists) {
  git -C $repoRoot branch "codex/integration-app"
}

$branchExists = ((git -C $repoRoot branch --list $branchName) | Out-String).Trim()
if (-not $branchExists) {
  git -C $repoRoot branch $branchName "codex/integration-app"
}

Write-Host "Issue note: $issuePath"
Write-Host "Branch: $branchName"
