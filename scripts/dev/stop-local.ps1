param(
  [int]$FrontendPort = 3010,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot

foreach ($port in @($FrontendPort, $BackendPort)) {
  $listener = Get-PortListener -Port $port
  if ($null -ne $listener) {
    Stop-PortListenerProcess -Port $port
    Wait-ForPortClosed -Port $port
    Write-Host "Stopped process on port $port"
  }
}

Push-Location $repoRoot
try {
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"
  docker compose stop postgres redis | Out-Null
} finally {
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Stopped local infrastructure"
