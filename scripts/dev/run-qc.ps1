param(
  [switch]$StartStack,
  [int]$FrontendPort = 3010,
  [int]$FrontendProdPort = 3110,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379
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
$playwrightOutputDir = Join-Path $frontendDir "output\\playwright"

function Start-FrontendDev {
  param([int]$Port)

  $frontendCmd = @(
    "set ""NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$BackendPort""",
    "set ""NEXT_PUBLIC_WS_URL=ws://127.0.0.1:$BackendPort/ws/cockpit""",
    "npm run dev -- --port $Port"
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
  $env:BROWSER_SMOKE_LABEL = $Label
  node ..\scripts\dev\browser-smoke.mjs

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
    -RedisPort $RedisPort
}

Push-Location $backendDir
try {
  python -m pytest -q
} finally {
  Pop-Location
}

Push-Location $frontendDir
try {
  npm run lint
  npm run typecheck
  npm run test

  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendPort" -Label "dev-smoke-initial"

  Stop-PortListenerProcess -Port $FrontendPort
  Wait-ForPortClosed -Port $FrontendPort

  $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$BackendPort"
  $env:NEXT_PUBLIC_WS_URL = "ws://127.0.0.1:$BackendPort/ws/cockpit"
  npm run build

  Start-FrontendProd -Port $FrontendProdPort
  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendProdPort" -Label "prod-smoke"

  Stop-PortListenerProcess -Port $FrontendProdPort
  Wait-ForPortClosed -Port $FrontendProdPort

  Start-FrontendDev -Port $FrontendPort
  Invoke-BrowserSmoke -Url "http://127.0.0.1:$FrontendPort" -Label "dev-smoke-final"
  $env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
  node ..\scripts\dev\fidelity-baselines.mjs
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BROWSER_SMOKE_LABEL -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_WS_URL -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Local QC completed successfully"
