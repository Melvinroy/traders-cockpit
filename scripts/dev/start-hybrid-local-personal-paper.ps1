param(
  [int]$FrontendPort = 3010,
  [int]$FrontendProdPort = 3110,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379,
  [string]$EnvFile = ".env.personal-paper.local"
)

$ErrorActionPreference = "Stop"

Write-Host "Starting hybrid local personal-paper mode"
Write-Host "Frontend/backend run locally; Postgres/Redis run in Docker"

& (Join-Path $PSScriptRoot "check-local-paper-readiness.ps1") -EnvFile $EnvFile
& (Join-Path $PSScriptRoot "start-local-personal-paper.ps1") `
  -FrontendPort $FrontendPort `
  -FrontendProdPort $FrontendProdPort `
  -BackendPort $BackendPort `
  -PostgresPort $PostgresPort `
  -RedisPort $RedisPort `
  -EnvFile $EnvFile
