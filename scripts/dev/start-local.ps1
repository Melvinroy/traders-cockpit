param(
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
$backendOut = Join-Path $repoRoot "backend.out.log"
$backendErr = Join-Path $repoRoot "backend.err.log"
$frontendOut = Join-Path $repoRoot "frontend.out.log"
$frontendErr = Join-Path $repoRoot "frontend.err.log"

Assert-PortFree -Port $FrontendPort -Purpose "Frontend"
Assert-PortFree -Port $BackendPort -Purpose "Backend"
Assert-PortFree -Port $PostgresPort -Purpose "Postgres"
Assert-PortFree -Port $RedisPort -Purpose "Redis"

Push-Location $repoRoot
try {
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"
  docker compose up -d postgres redis
} finally {
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

Wait-ForPort -Port $PostgresPort
Wait-ForPort -Port $RedisPort
Push-Location $repoRoot
try {
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"
  Wait-ForCommandSuccess -Description "postgres readiness" -ScriptBlock {
    docker compose exec -T postgres pg_isready -U traders_cockpit -d traders_cockpit
  }
} finally {
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

$backendCmd = @(
  "set ""DATABASE_URL=postgresql://traders_cockpit:traders_cockpit@127.0.0.1:$PostgresPort/traders_cockpit""",
  "set ""REDIS_URL=redis://127.0.0.1:$RedisPort/0""",
  "set ""CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort""",
  "alembic upgrade head",
  "python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort"
) -join " && "

Start-Process -FilePath "cmd.exe" `
  -WorkingDirectory $backendDir `
  -ArgumentList "/c", $backendCmd `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -WindowStyle Hidden

Wait-ForHttp -Url "http://127.0.0.1:$BackendPort/health"

$frontendCmd = @(
  "set ""NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$BackendPort""",
  "set ""NEXT_PUBLIC_WS_URL=ws://127.0.0.1:$BackendPort/ws/cockpit""",
  "npm run dev -- --port $FrontendPort"
) -join " && "

Start-Process -FilePath "cmd.exe" `
  -WorkingDirectory $frontendDir `
  -ArgumentList "/c", $frontendCmd `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr `
  -WindowStyle Hidden

Wait-ForHttp -Url "http://127.0.0.1:$FrontendPort"

Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
