param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8000,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379,
  [string]$EnvFile = ".env.personal-paper.local",
  [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }

$composeArgs = @(
  "compose",
  "--env-file", $envPath,
  "down"
)
if ($RemoveVolumes) {
  $composeArgs += "--volumes"
}

Push-Location $repoRoot
try {
  $env:FRONTEND_HOST_PORT = "$FrontendPort"
  $env:BACKEND_HOST_PORT = "$BackendPort"
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"

  docker @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed."
  }
} finally {
  Remove-Item Env:FRONTEND_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host "Docker local personal-paper stack stopped"
