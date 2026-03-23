param(
  [string]$EnvFile = ".env"
)

$repoRoot = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
$target = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }

if (-not (Test-Path $target)) {
  throw "Env file not found: $target"
}

$required = @(
  "APP_ENV",
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_WS_URL",
  "DATABASE_URL",
  "REDIS_URL",
  "CORS_ORIGINS",
  "AUTH_REQUIRE_LOGIN",
  "AUTH_COOKIE_SAMESITE",
  "AUTH_COOKIE_SECURE",
  "AUTH_STORAGE_MODE",
  "ALLOW_SQLITE_FALLBACK",
  "AUTH_ADMIN_USERNAME",
  "AUTH_ADMIN_PASSWORD",
  "AUTH_TRADER_USERNAME",
  "AUTH_TRADER_PASSWORD"
)

function Read-BoolValue {
  param([string]$Value, [bool]$Default = $false)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return @("1", "true", "yes", "on") -contains $Value.Trim().ToLowerInvariant()
}

$envMap = @{}
Get-Content $target | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
    return
  }
  $parts = $line.Split("=", 2)
  $envMap[$parts[0].Trim()] = $parts[1].Trim()
}

$missing = @()
foreach ($key in $required) {
  if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
    $missing += $key
  }
}

if ($missing.Count -gt 0) {
  throw ("Missing hosted env values: " + ($missing -join ", "))
}

$appEnv = $envMap["APP_ENV"].Trim().ToLowerInvariant()
if ($appEnv -notin @("staging", "production")) {
  throw "APP_ENV must be staging or production for hosted validation: $($envMap["APP_ENV"])"
}

$publicValues = @("NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_WS_URL", "CORS_ORIGINS")
foreach ($key in $publicValues) {
  $value = $envMap[$key]
  if ($value -match "127\\.0\\.0\\.1|localhost") {
    throw "$key cannot point to localhost for a hosted deployment: $value"
  }
}

foreach ($key in @("DATABASE_URL", "REDIS_URL")) {
  $value = $envMap[$key]
  if ($value -match "127\\.0\\.0\\.1|localhost") {
    throw "$key cannot point to localhost for a hosted deployment: $value"
  }
}

if (-not (Read-BoolValue -Value $envMap["AUTH_REQUIRE_LOGIN"] -Default $false)) {
  throw "AUTH_REQUIRE_LOGIN must be true for hosted deployment."
}

if (-not (Read-BoolValue -Value $envMap["AUTH_COOKIE_SECURE"] -Default $false)) {
  throw "AUTH_COOKIE_SECURE must be true for hosted deployment."
}

$sameSite = $envMap["AUTH_COOKIE_SAMESITE"].Trim().ToLowerInvariant()
if ($sameSite -notin @("lax", "strict", "none")) {
  throw "AUTH_COOKIE_SAMESITE must be one of lax, strict, or none."
}
if ($sameSite -eq "none" -and -not (Read-BoolValue -Value $envMap["AUTH_COOKIE_SECURE"] -Default $false)) {
  throw "AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE=none."
}

if (Read-BoolValue -Value $envMap["ALLOW_SQLITE_FALLBACK"] -Default $false) {
  throw "ALLOW_SQLITE_FALLBACK must be false for hosted deployment."
}

if ($envMap["DATABASE_URL"].Trim().ToLowerInvariant().StartsWith("sqlite")) {
  throw "DATABASE_URL cannot use sqlite for hosted deployment."
}

$authStorageMode = $envMap["AUTH_STORAGE_MODE"].Trim().ToLowerInvariant()
if ($authStorageMode -ne "database") {
  throw "AUTH_STORAGE_MODE must be database for hosted deployment."
}

if ($envMap.ContainsKey("ALLOW_LIVE_TRADING") -and (Read-BoolValue -Value $envMap["ALLOW_LIVE_TRADING"] -Default $false)) {
  if (-not $envMap.ContainsKey("LIVE_CONFIRMATION_TOKEN") -or [string]::IsNullOrWhiteSpace($envMap["LIVE_CONFIRMATION_TOKEN"])) {
    throw "LIVE_CONFIRMATION_TOKEN must be set when ALLOW_LIVE_TRADING=true."
  }
}

Write-Host "Hosted env check passed for $target"
