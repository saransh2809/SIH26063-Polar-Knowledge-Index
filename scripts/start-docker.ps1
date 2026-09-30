# Start Docker Desktop and the database, working around a Docker Desktop bug on this machine:
# after an unclean shutdown it leaves socket files it cannot remove, and then crashes on start
# ("initializing Inference manager" / "initializing Secrets Engine ... engine.sock").
# The stale folders are renamed aside (never deleted); Docker recreates them.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start-docker.ps1

$ErrorActionPreference = 'Stop'
$docker = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

function Test-Engine {
    # Windows PowerShell 5.1 turns a native command's stderr into an error under 'Stop'.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    docker version --format '{{.Server.Version}}' 2>&1 | Out-Null
    $ok = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $prev
    return $ok
}

if (-not (Test-Engine)) {
    Get-Process | Where-Object { $_.ProcessName -match '^Docker Desktop$|^com\.docker' } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 3
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    foreach ($dir in @("$env:LOCALAPPDATA\Docker\run", "$env:LOCALAPPDATA\docker-secrets-engine")) {
        if (Test-Path $dir) {
            Rename-Item $dir ((Split-Path $dir -Leaf) + ".stale-$stamp")
            Write-Host "Moved aside stale folder: $dir"
        }
    }
    Start-Process $docker
    Write-Host 'Waiting for the Docker engine...'
    for ($i = 0; $i -lt 60 -and -not (Test-Engine); $i++) { Start-Sleep 5 }
    if (-not (Test-Engine)) { throw 'Docker did not start. Open Docker Desktop to see its error.' }
}
Write-Host 'Docker engine is running.'

Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose up -d
Write-Host 'Database container started (ncpor-db).'
