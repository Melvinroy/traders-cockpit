param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8000,
  [int]$PostgresPort = 55432,
  [int]$RedisPort = 56379,
  [string]$EnvFile = ".env.personal-paper.local",
  [switch]$StartStack,
  [switch]$Build
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $envPath -PersonalPaper
$qcAuthUsername = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_USERNAME" -Default "admin"
$qcAuthPassword = Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_PASSWORD" -Default "admin123!"

if ($StartStack) {
  & (Join-Path $PSScriptRoot "start-docker-local-personal-paper.ps1") `
    -FrontendPort $FrontendPort `
    -BackendPort $BackendPort `
    -PostgresPort $PostgresPort `
    -RedisPort $RedisPort `
    -EnvFile $envPath `
    -Build:$Build
}

$env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
$env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
$env:QC_AUTH_USERNAME = $qcAuthUsername
$env:QC_AUTH_PASSWORD = $qcAuthPassword

try {
  node (Join-Path $PSScriptRoot "docker-local-paper-smoke.mjs")
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_USERNAME -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_PASSWORD -ErrorAction SilentlyContinue
}
