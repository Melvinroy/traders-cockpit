param(
  [switch]$DeleteMergedLocalBranches,
  [switch]$DeleteMergedRemoteBranches,
  [switch]$PruneOrigin
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
Push-Location $repoRoot
try {
  if ($PruneOrigin) {
    git remote prune origin | Out-Null
  }

  $currentBranch = (git branch --show-current).Trim()
  $protectedLocal = @("main", "codex/integration-app", $currentBranch)
  $protectedRemote = @("origin/main", "origin/codex/integration-app", "origin/HEAD")

  $mergedLocal = @(
    git for-each-ref refs/heads/codex --format="%(refname:short)" --merged main |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_ -and ($_ -notin $protectedLocal) }
  )

  $mergedRemote = @(
    git branch -r --merged main |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_ -like "origin/codex/*" -and ($_ -notin $protectedRemote) }
  )

  $issueDocs = Get-ChildItem (Join-Path $repoRoot "docs\issues") -File |
    Where-Object { $_.Name -ne "TEMPLATE.md" }
  $docsMissingStatus = @()
  $docsNotClosed = @()
  foreach ($doc in $issueDocs) {
    $head = Get-Content $doc.FullName -TotalCount 8
    $statusLine = $head | Where-Object { $_ -match "^> Status:" } | Select-Object -First 1
    if (-not $statusLine) {
      $docsMissingStatus += $doc.Name
      continue
    }
    if ($statusLine -notmatch "Closed") {
      $docsNotClosed += "$($doc.Name): $statusLine"
    }
  }

  Write-Host "Merged local feature branches reachable from main:"
  if ($mergedLocal.Count -eq 0) {
    Write-Host "- none"
  } else {
    $mergedLocal | ForEach-Object { Write-Host "- $_" }
  }

  Write-Host ""
  Write-Host "Merged remote feature branches reachable from main:"
  if ($mergedRemote.Count -eq 0) {
    Write-Host "- none"
  } else {
    $mergedRemote | ForEach-Object { Write-Host "- $_" }
  }

  Write-Host ""
  Write-Host "Issue docs missing a lifecycle status header:"
  if ($docsMissingStatus.Count -eq 0) {
    Write-Host "- none"
  } else {
    $docsMissingStatus | ForEach-Object { Write-Host "- $_" }
  }

  Write-Host ""
  Write-Host "Issue docs not marked closed:"
  if ($docsNotClosed.Count -eq 0) {
    Write-Host "- none"
  } else {
    $docsNotClosed | ForEach-Object { Write-Host "- $_" }
  }

  if ($DeleteMergedLocalBranches) {
    foreach ($branch in $mergedLocal) {
      git branch -d $branch
    }
  }

  if ($DeleteMergedRemoteBranches) {
    foreach ($branch in $mergedRemote) {
      $remoteName = $branch.Substring("origin/".Length)
      git push origin --delete $remoteName
    }
  }
} finally {
  Pop-Location
}
