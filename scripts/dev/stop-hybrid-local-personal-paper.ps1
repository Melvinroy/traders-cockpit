param(
  [int]$FrontendPort = 3010,
  [int]$BackendPort = 8010,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping hybrid local personal-paper mode"
& (Join-Path $PSScriptRoot "stop-local.ps1") `
  -FrontendPort $FrontendPort `
  -BackendPort $BackendPort `
  -PostgresPort $PostgresPort `
  -RedisPort $RedisPort
