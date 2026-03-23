param(
  [Parameter(Mandatory = $true)]
  [string]$FrontendUrl,

  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,

  [string]$EnvFile = ".env.production.local",
  [string]$SmokeLabel = "hosted-smoke",
  [string]$Symbol = "MSFT",
  [string]$AuthUsername,
  [string]$AuthPassword
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $EnvFile
$frontendDir = Join-Path $repoRoot "frontend"
$playwrightOutputDir = Join-Path $frontendDir "output\\playwright"
$healthArtifact = Join-Path $playwrightOutputDir "$SmokeLabel.health.json"

$env:FRONTEND_URL = $FrontendUrl
$env:BACKEND_URL = $BackendUrl.TrimEnd("/")
$env:BROWSER_SMOKE_LABEL = $SmokeLabel
$env:QC_SYMBOL = $Symbol.Trim().ToUpperInvariant()
$env:QC_AUTH_USERNAME = if ($AuthUsername) {
  $AuthUsername
} else {
  Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_USERNAME" -Default "admin"
}
$env:QC_AUTH_PASSWORD = if ($AuthPassword) {
  $AuthPassword
} else {
  Get-ResolvedValue -EnvValues $profileEnv -Key "AUTH_ADMIN_PASSWORD" -Default "change-me-admin"
}

function Read-HttpErrorBody {
  param($Exception)

  if ($null -eq $Exception.Response) {
    return ""
  }

  try {
    $stream = $Exception.Response.GetResponseStream()
    if ($null -eq $stream) {
      return ""
    }
    $reader = New-Object System.IO.StreamReader($stream)
    try {
      return $reader.ReadToEnd()
    } finally {
      $reader.Dispose()
    }
  } catch {
    return ""
  }
}

function Invoke-HostedHealthCheck {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$ExpectedKind
  )

  $requestId = "hosted-smoke-$Name-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
  $bodyText = ""
  $statusCode = 0

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers @{ "X-Request-ID" = $requestId } -TimeoutSec 10
    $statusCode = [int]$response.StatusCode
    $bodyText = $response.Content
  } catch {
    if ($_.Exception.Response) {
      $statusCode = [int]$_.Exception.Response.StatusCode
      $bodyText = Read-HttpErrorBody -Exception $_.Exception
    } else {
      throw
    }
  }

  $payload = $null
  if ($bodyText) {
    try {
      $payload = $bodyText | ConvertFrom-Json
    } catch {
      $payload = [ordered]@{ raw = $bodyText }
    }
  }

  $issues = @()
  if ($statusCode -ne 200) {
    $issues += "expected HTTP 200 but received $statusCode"
  }
  if ($null -eq $payload) {
    $issues += "missing JSON payload"
  } else {
    if ($payload.PSObject.Properties.Name -contains "kind" -and $payload.kind -ne $ExpectedKind) {
      $issues += "expected payload kind '$ExpectedKind' but received '$($payload.kind)'"
    }
    if ($payload.PSObject.Properties.Name -contains "status" -and $payload.status -ne "ok") {
      $issues += "expected payload status 'ok' but received '$($payload.status)'"
    }
  }

  return [ordered]@{
    name = $Name
    url = $Url
    requestId = $requestId
    statusCode = $statusCode
    ok = ($issues.Count -eq 0)
    issues = $issues
    payload = $payload
  }
}

try {
  New-Item -ItemType Directory -Force -Path $playwrightOutputDir | Out-Null

  Push-Location $repoRoot
  try {
    & (Join-Path $PSScriptRoot "check-hosted-env.ps1") -EnvFile $EnvFile
  } finally {
    Pop-Location
  }

  $backendBaseUrl = $env:BACKEND_URL
  $healthChecks = @(
    Invoke-HostedHealthCheck -Name "live" -Url "$backendBaseUrl/health/live" -ExpectedKind "live"
    Invoke-HostedHealthCheck -Name "ready" -Url "$backendBaseUrl/health/ready" -ExpectedKind "ready"
    Invoke-HostedHealthCheck -Name "deps" -Url "$backendBaseUrl/health/deps" -ExpectedKind "deps"
  )
  $healthReport = [ordered]@{
    label = $SmokeLabel
    checkedAt = (Get-Date).ToString("o")
    frontendUrl = $FrontendUrl
    backendUrl = $backendBaseUrl
    checks = $healthChecks
  }
  $healthReport | ConvertTo-Json -Depth 20 | Set-Content -Path $healthArtifact -Encoding UTF8

  $failedChecks = @($healthChecks | Where-Object { -not $_.ok })
  if ($failedChecks.Count -gt 0) {
    $failureSummary = ($failedChecks | ForEach-Object {
      "$($_.name): $($_.issues -join '; ')"
    }) -join "`n"
    throw "Hosted smoke health checks failed.`n$failureSummary"
  }

  Push-Location $frontendDir
  try {
    node ..\scripts\dev\browser-smoke.mjs
  } finally {
    Pop-Location
  }

  foreach ($suffix in @("health.json", "png", "console.txt", "network.txt")) {
    $artifact = Join-Path $playwrightOutputDir "$SmokeLabel.$suffix"
    if (-not (Test-Path $artifact)) {
      throw "Expected hosted smoke artifact was not created: $artifact"
    }
  }

  Write-Host "Hosted smoke completed successfully"
  Write-Host "Artifacts: $playwrightOutputDir"
} finally {
  Remove-Item Env:FRONTEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BACKEND_URL -ErrorAction SilentlyContinue
  Remove-Item Env:BROWSER_SMOKE_LABEL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_SYMBOL -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_USERNAME -ErrorAction SilentlyContinue
  Remove-Item Env:QC_AUTH_PASSWORD -ErrorAction SilentlyContinue
}
