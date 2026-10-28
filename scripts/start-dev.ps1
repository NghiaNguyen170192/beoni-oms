$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

foreach ($command in @("docker", "bun")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command '$command' was not found on PATH."
    }
}

Push-Location $repoRoot
try {
    & docker compose stop frontend
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stop the Compose frontend service."
    }
}
finally {
    Pop-Location
}

Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-NoExit", "-Command", "docker compose up --watch backend")

Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-NoExit", "-Command", "bun run dev")

Write-Host "Backend watch and frontend dev server started in separate PowerShell windows."
Write-Host "Frontend: http://localhost:5173 | Backend: http://localhost:8000"
