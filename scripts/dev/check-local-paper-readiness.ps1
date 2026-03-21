param(
  [string]$EnvFile,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = Get-RepoRoot
$profileEnv = Get-LocalProfileEnv -RepoRoot $repoRoot -EnvFile $EnvFile -PersonalPaper

function Read-BoolValue {
  param([string]$Value, [bool]$Default = $false)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return @("1", "true", "yes", "on") -contains $Value.Trim().ToLowerInvariant()
}

$brokerMode = Get-ResolvedValue -EnvValues $profileEnv -Key "BROKER_MODE" -Default "paper"
$allowLiveTrading = Read-BoolValue -Value (Get-ResolvedValue -EnvValues $profileEnv -Key "ALLOW_LIVE_TRADING" -Default "false")
$alpacaKeyId = Get-ResolvedValue -EnvValues $profileEnv -Key "ALPACA_API_KEY_ID"
$alpacaSecret = Get-ResolvedValue -EnvValues $profileEnv -Key "ALPACA_API_SECRET_KEY"
$defaultEquity = Get-ResolvedValue -EnvValues $profileEnv -Key "DEFAULT_ACCOUNT_EQUITY" -Default "100000"
$defaultRiskPct = Get-ResolvedValue -EnvValues $profileEnv -Key "DEFAULT_RISK_PCT" -Default "1"
$maxPositionNotionalPct = Get-ResolvedValue -EnvValues $profileEnv -Key "MAX_POSITION_NOTIONAL_PCT" -Default "100"
$dailyLossLimitPct = Get-ResolvedValue -EnvValues $profileEnv -Key "DAILY_LOSS_LIMIT_PCT" -Default "2"
$maxOpenPositions = Get-ResolvedValue -EnvValues $profileEnv -Key "MAX_OPEN_POSITIONS" -Default "6"

$issues = @()
if ($brokerMode -ne "alpaca_paper") {
  $issues += "BROKER_MODE must be alpaca_paper for local personal-paper mode."
}
if ($allowLiveTrading) {
  $issues += "ALLOW_LIVE_TRADING must remain false for local personal-paper mode."
}
if (Read-BoolValue -Value (Get-ResolvedValue -EnvValues $profileEnv -Key "ALLOW_CONTROLLER_MOCK" -Default "false") -Default $false) {
  $issues += "ALLOW_CONTROLLER_MOCK must be false for the real local personal-paper mode."
}
if ([string]::IsNullOrWhiteSpace($alpacaKeyId) -or [string]::IsNullOrWhiteSpace($alpacaSecret)) {
  $issues += "ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY must be set."
}
foreach ($numericCheck in @(
    @{ Key = "DEFAULT_ACCOUNT_EQUITY"; Value = $defaultEquity; Minimum = 1.0 },
    @{ Key = "DEFAULT_RISK_PCT"; Value = $defaultRiskPct; Minimum = 0.01 },
    @{ Key = "MAX_POSITION_NOTIONAL_PCT"; Value = $maxPositionNotionalPct; Minimum = 1.0 },
    @{ Key = "DAILY_LOSS_LIMIT_PCT"; Value = $dailyLossLimitPct; Minimum = 0.01 },
    @{ Key = "MAX_OPEN_POSITIONS"; Value = $maxOpenPositions; Minimum = 1.0 }
  )) {
  $parsed = 0.0
  if (-not [double]::TryParse("$($numericCheck.Value)", [ref]$parsed) -or $parsed -lt [double]$numericCheck.Minimum) {
    $issues += "$($numericCheck.Key) must be a valid value >= $($numericCheck.Minimum)."
  }
}

if ($issues.Count -gt 0) {
  $message = @("Local personal-paper readiness failed:") + ($issues | ForEach-Object { "- $_" })
  throw ($message -join [Environment]::NewLine)
}

if (-not $Quiet) {
  Write-Host "Local personal-paper readiness passed"
  Write-Host "Broker mode:          $brokerMode"
  Write-Host "Live trading enabled: $allowLiveTrading"
  Write-Host "Alpaca creds:         present"
  Write-Host "Default equity:       $defaultEquity"
  Write-Host "Default risk %:       $defaultRiskPct"
  Write-Host "Max notional %:       $maxPositionNotionalPct"
  Write-Host "Daily loss limit %:   $dailyLossLimitPct"
  Write-Host "Max open positions:   $maxOpenPositions"
}
