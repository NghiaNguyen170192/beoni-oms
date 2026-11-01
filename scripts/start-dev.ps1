
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

foreach ($command in @("docker", "bun")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Error "Required command '$command' was not found on PATH."
        exit 1
    }
}

docker compose stop frontend
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$backendProcess = Start-Process `
    -FilePath "docker" `
    -ArgumentList @("compose", "up", "--watch", "backend") `
    -WorkingDirectory $repoRoot `
    -NoNewWindow `
    -PassThru

try {
    Write-Host "Backend watch and frontend dev server started."
    Write-Host "Frontend: http://localhost:5173 | Backend: http://localhost:8000"

    bun run dev
    exit $LASTEXITCODE
}
finally {
    if (-not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
    }
}
