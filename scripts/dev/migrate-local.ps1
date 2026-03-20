param(
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"

Push-Location $backendDir
try {
  $env:DATABASE_URL = "postgresql://traders_cockpit:traders_cockpit@127.0.0.1:$PostgresPort/traders_cockpit"
  $env:REDIS_URL = "redis://127.0.0.1:$RedisPort/0"
  alembic upgrade head
} finally {
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_URL -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Applied Alembic migrations against local Postgres"
