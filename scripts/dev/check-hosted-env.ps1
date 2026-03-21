param(
  [string]$EnvFile = ".env"
)

$repoRoot = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
$target = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }

if (-not (Test-Path $target)) {
  throw "Env file not found: $target"
}

$required = @(
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_WS_URL",
  "DATABASE_URL",
  "REDIS_URL",
  "CORS_ORIGINS",
  "AUTH_ADMIN_USERNAME",
  "AUTH_ADMIN_PASSWORD"
)

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

$publicValues = @("NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_WS_URL", "CORS_ORIGINS")
foreach ($key in $publicValues) {
  $value = $envMap[$key]
  if ($value -match "127\\.0\\.0\\.1|localhost") {
    throw "$key cannot point to localhost for a hosted deployment: $value"
  }
}

Write-Host "Hosted env check passed for $target"
