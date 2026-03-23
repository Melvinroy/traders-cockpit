param(
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
$frontendNextDir = Join-Path $frontendDir ".next"
$backendOut = Join-Path $repoRoot "backend.out.log"
$backendErr = Join-Path $repoRoot "backend.err.log"
$frontendOut = Join-Path $repoRoot "frontend.out.log"
$frontendErr = Join-Path $repoRoot "frontend.err.log"
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $EnvFile -PersonalPaper:$PersonalPaper

if ($PersonalPaper) {
  & (Join-Path $PSScriptRoot "check-local-paper-readiness.ps1") -EnvFile $EnvFile -Quiet
}

Assert-PortFree -Port $FrontendPort -Purpose "Frontend"
Assert-PortFree -Port $BackendPort -Purpose "Backend"
Assert-PortFree -Port $PostgresPort -Purpose "Postgres"
Assert-PortFree -Port $RedisPort -Purpose "Redis"

Push-Location $repoRoot
try {
  $env:POSTGRES_HOST_PORT = "$PostgresPort"
  $env:REDIS_HOST_PORT = "$RedisPort"
  cmd /c "docker compose up -d postgres redis"
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed with exit code $LASTEXITCODE."
  }
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
    cmd /c "docker compose exec -T postgres pg_isready -U traders_cockpit -d traders_cockpit"
  }
} finally {
  Remove-Item Env:POSTGRES_HOST_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:REDIS_HOST_PORT -ErrorAction SilentlyContinue
  Pop-Location
}

$backendRuntimeEnv = @{}
foreach ($entry in $profileEnv.GetEnumerator()) {
  if ($entry.Key -in @("DATABASE_URL", "REDIS_URL", "CORS_ORIGINS", "NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_WS_URL")) {
    continue
  }
  $backendRuntimeEnv[$entry.Key] = $entry.Value
}
$backendRuntimeEnv["DATABASE_URL"] = "postgresql://traders_cockpit:change-me-postgres@127.0.0.1:$PostgresPort/traders_cockpit"
$backendRuntimeEnv["REDIS_URL"] = "redis://127.0.0.1:$RedisPort/0"
$backendRuntimeEnv["CORS_ORIGINS"] = "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort,http://127.0.0.1:$FrontendProdPort,http://localhost:$FrontendProdPort"

if ($PersonalPaper) {
  $backendRuntimeEnv["BROKER_MODE"] = "alpaca_paper"
  $backendRuntimeEnv["ALLOW_LIVE_TRADING"] = "false"
  if (-not $backendRuntimeEnv.ContainsKey("ALLOW_CONTROLLER_MOCK")) {
    $backendRuntimeEnv["ALLOW_CONTROLLER_MOCK"] = "true"
  }
}

$backendCmdParts = @()
$backendCmdParts += Convert-EnvMapToCmdSetStatements -EnvValues $backendRuntimeEnv
$backendCmdParts += @(
  "alembic upgrade head",
  "python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort"
)
$backendCmd = $backendCmdParts -join " && "

Start-Process -FilePath "cmd.exe" `
  -WorkingDirectory $backendDir `
  -ArgumentList "/c", $backendCmd `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -WindowStyle Hidden

Wait-ForHttp -Url "http://127.0.0.1:$BackendPort/health"

$authAdminUsername = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_USERNAME" -Default "admin"
$authAdminPassword = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_PASSWORD" -Default "change-me-admin"
$accountMode = if ($PersonalPaper) { "alpaca_paper" } else { "paper" }
$defaultEquity = [double](Get-ResolvedValue -EnvValues $profileEnv -Key "DEFAULT_ACCOUNT_EQUITY" -Default "100000")
$defaultRiskPct = [double](Get-ResolvedValue -EnvValues $profileEnv -Key "DEFAULT_RISK_PCT" -Default "1")
$accountBody = @{
  equity = $defaultEquity
  risk_pct = $defaultRiskPct
  mode = $accountMode
} | ConvertTo-Json

$authSession = $null
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:$BackendPort/api/auth/login" `
  -ContentType "application/json" `
  -Body (@{ username = $authAdminUsername; password = $authAdminPassword } | ConvertTo-Json) `
  -SessionVariable authSession | Out-Null

Invoke-RestMethod `
  -Method Put `
  -Uri "http://127.0.0.1:$BackendPort/api/account/settings" `
  -ContentType "application/json" `
  -Body $accountBody `
  -WebSession $authSession | Out-Null

if (Test-Path $frontendNextDir) {
  cmd /c "rmdir /s /q ""$frontendNextDir""" | Out-Null
}

$frontendCmd = @(
  "set ""NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$BackendPort""",
  "set ""NEXT_PUBLIC_WS_URL=ws://127.0.0.1:$BackendPort/ws/cockpit""",
  "npx next dev -p $FrontendPort"
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
