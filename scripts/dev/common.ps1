function Get-RepoRoot {
  return Resolve-Path (Join-Path $PSScriptRoot "..\\..")
}

function Read-EnvFileValues {
  param([Parameter(Mandatory = $true)][string]$Path)

  $values = @{}
  if (-not (Test-Path $Path)) {
    return $values
  }

  foreach ($rawLine in Get-Content $Path) {
    $line = $rawLine.Trim()
    if (-not $line -or $line.StartsWith("#")) {
      continue
    }
    if ($line.ToLower().StartsWith("export ")) {
      $line = $line.Substring(7).Trim()
    }
    $separatorIndex = $line.IndexOf("=")
    if ($separatorIndex -lt 1) {
      continue
    }
    $key = $line.Substring(0, $separatorIndex).Trim()
    $value = $line.Substring($separatorIndex + 1).Trim().Trim("'").Trim('"')
    if ($key) {
      $values[$key] = $value
    }
  }

  return $values
}

function Merge-EnvValues {
  param(
    [hashtable]$Base = @{},
    [hashtable]$Override = @{}
  )

  $merged = @{}
  foreach ($entry in $Base.GetEnumerator()) {
    $merged[$entry.Key] = $entry.Value
  }
  foreach ($entry in $Override.GetEnumerator()) {
    $merged[$entry.Key] = $entry.Value
  }
  return $merged
}

function Get-LocalProfileEnv {
  param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [string]$EnvFile,
    [switch]$PersonalPaper
  )

  $envValues = @{}
  $candidateFiles = @()
  if ($EnvFile) {
    $candidateFiles += $EnvFile
  } elseif ($PersonalPaper) {
    $candidateFiles += @(
      (Join-Path $RepoRoot ".env.personal-paper.local"),
      (Join-Path $RepoRoot ".env.personal-paper"),
      (Join-Path $RepoRoot "backend\.env.personal-paper.local"),
      (Join-Path $RepoRoot "backend\.env.personal-paper")
    )
  }

  foreach ($candidate in $candidateFiles) {
    $resolved = $candidate
    if (-not [System.IO.Path]::IsPathRooted($resolved)) {
      $resolved = Join-Path $RepoRoot $candidate
    }
    $envValues = Merge-EnvValues -Base $envValues -Override (Read-EnvFileValues -Path $resolved)
  }

  return $envValues
}

function Get-ResolvedValue {
  param(
    [hashtable]$EnvValues,
    [Parameter(Mandatory = $true)][string]$Key,
    [string]$Default = ""
  )

  if ($EnvValues.ContainsKey($Key) -and $null -ne $EnvValues[$Key] -and "$($EnvValues[$Key])".Trim()) {
    return "$($EnvValues[$Key])".Trim()
  }
  if (Test-Path "Env:$Key") {
    $value = (Get-Item "Env:$Key").Value
    if ($null -ne $value -and "$value".Trim()) {
      return "$value".Trim()
    }
  }
  return $Default
}

function Convert-EnvMapToCmdSetStatements {
  param([Parameter(Mandatory = $true)][hashtable]$EnvValues)

  $statements = @()
  foreach ($entry in $EnvValues.GetEnumerator()) {
    $escapedValue = "$($entry.Value)".Replace('"', '\"')
    $statements += "set ""$($entry.Key)=$escapedValue"""
  }
  return $statements
}

function Get-PortListener {
  param([Parameter(Mandatory = $true)][int]$Port)
  return Get-PortListeners -Port $Port | Select-Object -First 1
}

function Get-PortListeners {
  param([Parameter(Mandatory = $true)][int]$Port)
  $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
  $active = @()
  foreach ($listener in $listeners) {
    try {
      Get-Process -Id $listener.OwningProcess -ErrorAction Stop | Out-Null
      $active += $listener
    } catch {
    }
  }
  return $active
}

function Stop-PortListenerProcess {
  param([Parameter(Mandatory = $true)][int]$Port)

  $attempts = 0
  while ($attempts -lt 5) {
    $listeners = Get-PortListeners -Port $Port | Select-Object -ExpandProperty OwningProcess -Unique
    if ($null -eq $listeners -or $listeners.Count -eq 0) {
      return
    }

    foreach ($processId in $listeners) {
      if (-not $processId) {
        continue
      }
      try {
        taskkill /PID $processId /T /F | Out-Null
      } catch {
        try {
          Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        } catch {
        }
      }
    }

    Start-Sleep -Milliseconds 400
    if ($null -eq (Get-PortListener -Port $Port)) {
      return
    }
    $attempts += 1
  }

  throw "Failed to stop listener(s) on port $Port."
}

function Assert-PortFree {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$Purpose
  )

  $listener = Get-PortListener -Port $Port
  if ($null -ne $listener) {
    throw "$Purpose cannot start because port $Port is already in use by PID $($listener.OwningProcess). Run scripts/dev/stop-local.ps1 or choose another port."
  }
}

function Wait-ForHttp {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  throw "Timed out waiting for $Url"
}

function Wait-ForPort {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($null -ne (Get-PortListener -Port $Port)) {
      return
    }
    Start-Sleep -Milliseconds 500
  }

  throw "Timed out waiting for port $Port"
}

function Wait-ForPortClosed {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($null -eq (Get-PortListener -Port $Port)) {
      return
    }
    Start-Sleep -Milliseconds 500
  }

  throw "Timed out waiting for port $Port to close"
}

function Wait-ForCommandSuccess {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$ScriptBlock,
    [int]$TimeoutSeconds = 30,
    [string]$Description = "command"
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      & $ScriptBlock | Out-Null
      if ($LASTEXITCODE -eq 0) {
        return
      }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  }

  throw "Timed out waiting for $Description"
}
