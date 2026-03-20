function Get-RepoRoot {
  return Resolve-Path (Join-Path $PSScriptRoot "..\\..")
}

function Get-PortListener {
  param([Parameter(Mandatory = $true)][int]$Port)
  return Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Stop-PortListenerProcess {
  param([Parameter(Mandatory = $true)][int]$Port)

  $listener = Get-PortListener -Port $Port
  if ($null -ne $listener) {
    Stop-Process -Id $listener.OwningProcess -Force
  }
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
