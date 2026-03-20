param(
  [switch]$StartStack,
  [int]$FrontendPort = 3010,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
if ($StartStack -or $null -eq (Get-PortListener -Port $FrontendPort) -or $null -eq (Get-PortListener -Port $BackendPort)) {
  & (Join-Path $PSScriptRoot "start-local.ps1") `
    -FrontendPort $FrontendPort `
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
  $env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
  npm run browser:smoke
  npm run build
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Local QC completed successfully"
