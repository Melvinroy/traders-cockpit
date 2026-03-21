param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8000,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379,
  [string]$EnvFile = ".env.personal-paper.local",
  [switch]$Build
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }

& (Join-Path $PSScriptRoot "check-local-paper-readiness.ps1") -EnvFile $envPath

$composeArgs = @(
  "compose",
  "--env-file", $envPath,
  "up",
  "-d"
)
if ($Build) {
  $composeArgs += "--build"
}

Push-Location $repoRoot
try {
  $env:FRONTEND_HOST_PORT = "$FrontendPort"
  $env:BACKEND_HOST_PORT = "$BackendPort"
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"

  docker compose --env-file $envPath down --remove-orphans | Out-Null

  Assert-PortFree -Port $FrontendPort -Purpose "Docker local personal-paper frontend"
  Assert-PortFree -Port $BackendPort -Purpose "Docker local personal-paper backend"
  Assert-PortFree -Port $PostgresPort -Purpose "Docker local personal-paper postgres"
  Assert-PortFree -Port $RedisPort -Purpose "Docker local personal-paper redis"

  docker @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed."
  }
} finally {
  Remove-Item Env:FRONTEND_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

Wait-ForHttp -Url "http://127.0.0.1:$BackendPort/health" -TimeoutSeconds 120
Wait-ForHttp -Url "http://127.0.0.1:$FrontendPort" -TimeoutSeconds 180

Write-Host "Docker local personal-paper stack is ready"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
