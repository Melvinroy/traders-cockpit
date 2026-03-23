param(
  [switch]$StartStack,
  [int]$FrontendPort = 3010,
  [int]$FrontendProdPort = 3110,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379,
  [switch]$PersonalPaper,
  [string]$EnvFile
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$frontendOut = Join-Path $repoRoot "frontend.out.log"
$frontendErr = Join-Path $repoRoot "frontend.err.log"
$frontendProdOut = Join-Path $repoRoot "frontend.prod.out.log"
$frontendProdErr = Join-Path $repoRoot "frontend.prod.err.log"
$frontendNextDir = Join-Path $frontendDir ".next"
$playwrightOutputDir = Join-Path $frontendDir "output\\playwright"
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $EnvFile -PersonalPaper:$PersonalPaper
$qcAuthUsername = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_USERNAME" -Default "admin"
$qcAuthPassword = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_PASSWORD" -Default "change-me-admin"

function Assert-LastExitCode {
  param([Parameter(Mandatory = $true)][string]$Description)

  if ($LASTEXITCODE -ne 0) {
    throw "$Description failed with exit code $LASTEXITCODE."
  }
}

function Reset-FrontendNextCache {
  if (Test-Path $frontendNextDir) {
    cmd /c "rmdir /s /q ""$frontendNextDir""" | Out-Null
  }
}

function Start-FrontendDev {
  param([int]$Port)

  Reset-FrontendNextCache

  $frontendCmd = @(
    "set ""NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$BackendPort""",
    "set ""NEXT_PUBLIC_WS_URL=ws://127.0.0.1:$BackendPort/ws/cockpit""",
    "npx next dev -p $Port"
  ) -join " && "

  Start-Process -FilePath "cmd.exe" `
    -WorkingDirectory $frontendDir `
    -ArgumentList "/c", $frontendCmd `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden

  Wait-ForHttp -Url "http://127.0.0.1:$Port"
}

function Start-FrontendProd {
  param([int]$Port)

  Assert-PortFree -Port $Port -Purpose "Frontend production server"

  $frontendCmd = @(
    "set ""NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$BackendPort""",
    "set ""NEXT_PUBLIC_WS_URL=ws://127.0.0.1:$BackendPort/ws/cockpit""",
    "npm run start -- --port $Port"
  ) -join " && "

  Start-Process -FilePath "cmd.exe" `
    -WorkingDirectory $frontendDir `
    -ArgumentList "/c", $frontendCmd `
    -RedirectStandardOutput $frontendProdOut `
    -RedirectStandardError $frontendProdErr `
    -WindowStyle Hidden

  Wait-ForHttp -Url "http://127.0.0.1:$Port"
}

function Invoke-BrowserSmoke {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $env:FRONTEND_URL = $Url
  $env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
  $env:NEXT_PUBLIC_API_BASE_URL = $env:BACKEND_URL
  $env:NEXT_PUBLIC_WS_URL = "ws://127.0.0.1:$BackendPort/ws/cockpit"
  $env:BROWSER_SMOKE_LABEL = $Label
  node ..\scripts\dev\browser-smoke.mjs
  Assert-LastExitCode -Description "Browser smoke ($Label)"

  foreach ($suffix in @("png", "console.txt", "network.txt")) {
    $artifact = Join-Path $playwrightOutputDir "$Label.$suffix"
    if (-not (Test-Path $artifact)) {
      throw "Expected browser smoke artifact was not created: $artifact"
    }
  }
}

if ($StartStack -or $null -eq (Get-PortListener -Port $FrontendPort) -or $null -eq (Get-PortListener -Port $BackendPort)) {
  & (Join-Path $PSScriptRoot "start-local.ps1") `
    -FrontendPort $FrontendPort `
    -FrontendProdPort $FrontendProdPort `
    -BackendPort $BackendPort `
    -PostgresPort $PostgresPort `
    -RedisPort $RedisPort `
    -PersonalPaper:$PersonalPaper `
    -EnvFile $EnvFile
}

if ($PersonalPaper) {
  & (Join-Path $PSScriptRoot "check-local-paper-readiness.ps1") -EnvFile $EnvFile -Quiet
}

Push-Location $backendDir
try {
  python -m pytest -q
  Assert-LastExitCode -Description "Backend pytest"
} finally {
  Pop-Location
}

Push-Location $frontendDir
try {
  $env:QC_AUTH_USERNAME = $qcAuthUsername
  $env:QC_AUTH_PASSWORD = $qcAuthPassword
  npm run lint
  Assert-LastExitCode -Description "Frontend lint"
  npm run typecheck
  Assert-LastExitCode -Description "Frontend typecheck"
  npm run test
  Assert-LastExitCode -Description "Frontend test"

  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendPort" -Label "dev-smoke-initial"

  Stop-PortListenerProcess -Port $FrontendPort
  Wait-ForPortClosed -Port $FrontendPort

  $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$BackendPort"
  $env:NEXT_PUBLIC_WS_URL = "ws://127.0.0.1:$BackendPort/ws/cockpit"
  npm run build
  Assert-LastExitCode -Description "Frontend build"

  Start-FrontendProd -Port $FrontendProdPort
  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendProdPort" -Label "prod-smoke"

  Stop-PortListenerProcess -Port $FrontendProdPort
  Wait-ForPortClosed -Port $FrontendProdPort

  Start-FrontendDev -Port $FrontendPort
  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendPort" -Label "dev-smoke-final"
  $env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
  $env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
  node ..\scripts\dev\fidelity-baselines.mjs
  Assert-LastExitCode -Description "Fidelity baselines"
  node ..\scripts\dev\trade-flow-qc.mjs
  Assert-LastExitCode -Description "Trade flow QC"
  foreach ($artifactName in @("baseline-idle.png", "baseline-setup-loaded.png", "baseline-trade-entered.png", "baseline-protected.png", "baseline-profit-flow.png")) {
    $artifact = Join-Path $playwrightOutputDir $artifactName
    if (-not (Test-Path $artifact)) {
      throw "Expected fidelity artifact was not created: $artifact"
    }
  }
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BROWSER_SMOKE_LABEL -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_WS_URL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_USERNAME -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Local QC completed successfully"
