# EdgeErgo V3 — Developer Script for Windows PowerShell
param (
    [Parameter(Position=0)]
    [ValidateSet("setup", "lint", "typecheck", "test", "build", "check-secrets", "all")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

Write-Host ">>> Running EdgeErgo V3 target: $Target" -ForegroundColor Cyan

function Run-CheckSecrets {
    Write-Host "`n--- Scanning for secrets ---" -ForegroundColor Yellow
    python "$RootDir\scripts\check_secrets.py"
    if ($LASTEXITCODE -ne 0) { throw "Secret check failed" }
}

function Run-Setup {
    Write-Host "`n--- Setting up Backend ---" -ForegroundColor Yellow
    python -m pip install -e "$RootDir\backend"
    Write-Host "`n--- Setting up Edge Agent ---" -ForegroundColor Yellow
    python -m pip install -e "$RootDir\edge-agent"
    Write-Host "`n--- Setting up Frontend ---" -ForegroundColor Yellow
    Push-Location "$RootDir\frontend"
    npm install
    Pop-Location
}

function Run-Lint {
    Write-Host "`n--- Linting Backend ---" -ForegroundColor Yellow
    python -m ruff check "$RootDir\backend\app" "$RootDir\backend\tests"
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed" }

    Write-Host "`n--- Linting Edge Agent ---" -ForegroundColor Yellow
    python -m ruff check "$RootDir\edge-agent\edge_ergo" "$RootDir\edge-agent\tests"
    if ($LASTEXITCODE -ne 0) { throw "Edge agent lint failed" }

    Write-Host "`n--- Linting Frontend ---" -ForegroundColor Yellow
    Push-Location "$RootDir\frontend"
    npm run lint
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend lint failed" }
    Pop-Location
}

function Run-Typecheck {
    Write-Host "`n--- Type checking Backend ---" -ForegroundColor Yellow
    python -m mypy "$RootDir\backend\app" "$RootDir\backend\tests"
    if ($LASTEXITCODE -ne 0) { throw "Backend typecheck failed" }

    Write-Host "`n--- Type checking Edge Agent ---" -ForegroundColor Yellow
    python -m mypy "$RootDir\edge-agent\edge_ergo" "$RootDir\edge-agent\tests"
    if ($LASTEXITCODE -ne 0) { throw "Edge agent typecheck failed" }

    Write-Host "`n--- Type checking Frontend ---" -ForegroundColor Yellow
    Push-Location "$RootDir\frontend"
    npx tsc -b
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend typecheck failed" }
    Pop-Location
}

function Run-Test {
    Write-Host "`n--- Testing Backend ---" -ForegroundColor Yellow
    python -m pytest "$RootDir\backend\tests"
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }

    Write-Host "`n--- Testing Edge Agent ---" -ForegroundColor Yellow
    python -m pytest "$RootDir\edge-agent\tests"
    if ($LASTEXITCODE -ne 0) { throw "Edge agent tests failed" }

    Write-Host "`n--- Testing Frontend ---" -ForegroundColor Yellow
    Push-Location "$RootDir\frontend"
    npm run test
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend tests failed" }
    Pop-Location
}

function Run-Build {
    Write-Host "`n--- Building Frontend ---" -ForegroundColor Yellow
    Push-Location "$RootDir\frontend"
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend build failed" }
    Pop-Location
}

switch ($Target) {
    "setup"         { Run-Setup }
    "check-secrets" { Run-CheckSecrets }
    "lint"          { Run-Lint }
    "typecheck"     { Run-Typecheck }
    "test"          { Run-Test }
    "build"         { Run-Build }
    "all" {
        Run-CheckSecrets
        Run-Lint
        Run-Typecheck
        Run-Test
        Run-Build
        Write-Host "`n>>> All verification targets PASSED successfully!" -ForegroundColor Green
    }
}
