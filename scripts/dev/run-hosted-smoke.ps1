param(
  [Parameter(Mandatory = $true)]
  [string]$FrontendUrl,

  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,

  [string]$EnvFile = ".env.production.local",
  [string]$SmokeLabel = "hosted-smoke",
  [string]$Symbol = "MSFT",
  [string]$AuthUsername,
  [string]$AuthPassword
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $EnvFile
$frontendDir = Join-Path $repoRoot "frontend"
$playwrightOutputDir = Join-Path $frontendDir "output\\playwright"

$env:FRONTEND_URL = $FrontendUrl
$env:BACKEND_URL = $BackendUrl.TrimEnd("/")
$env:BROWSER_SMOKE_LABEL = $SmokeLabel
$env:QC_SYMBOL = $Symbol.Trim().ToUpperInvariant()
$env:QC_AUTH_USERNAME = if ($AuthUsername) {
  $AuthUsername
} else {
  Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_USERNAME" -Default "admin"
}
$env:QC_AUTH_PASSWORD = if ($AuthPassword) {
  $AuthPassword
} else {
  Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_PASSWORD" -Default "change-me-admin"
}

try {
  Push-Location $repoRoot
  try {
    & (Join-Path $PSScriptRoot "check-hosted-env.ps1") -EnvFile $EnvFile
  } finally {
    Pop-Location
  }

  Push-Location $frontendDir
  try {
    node ..\scripts\dev\browser-smoke.mjs
  } finally {
    Pop-Location
  }

  foreach ($suffix in @("png", "console.txt", "network.txt")) {
    $artifact = Join-Path $playwrightOutputDir "$SmokeLabel.$suffix"
    if (-not (Test-Path $artifact)) {
      throw "Expected hosted smoke artifact was not created: $artifact"
    }
  }

  Write-Host "Hosted smoke completed successfully"
  Write-Host "Artifacts: $playwrightOutputDir"
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BROWSER_SMOKE_LABEL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_SYMBOL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_USERNAME -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_PASSWORD -ErrorAction SilentlyContinue
}
