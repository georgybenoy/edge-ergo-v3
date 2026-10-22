# EdgeErgo V3 - Windows Desktop Agent Build & Validation Script
# Builds the standalone one-folder distribution using PyInstaller,
# inspects the dist bundle for zero secrets/databases, and verifies smoke execution.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "EdgeErgo V3 - Windows Edge Agent PyInstaller Build" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify Prerequisites
Write-Host "`n[1/5] Verifying build prerequisites..." -ForegroundColor Yellow
$PythonCmd = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $PythonCmd) {
    Write-Error "Python executable not found in PATH."
    exit 1
}

$PyInstallerCheck = python -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
if (-not $PyInstallerCheck) {
    Write-Error "PyInstaller is not installed in the active Python environment."
    exit 1
}
Write-Host "  Found Python: $(python --version)"
Write-Host "  Found PyInstaller: $PyInstallerCheck"

# 2. Clean Previous Build Artifacts
Write-Host "`n[2/5] Cleaning old build and dist directories..." -ForegroundColor Yellow
$BuildDir = Join-Path $RepoRoot "edge-agent\build"
$DistDir = Join-Path $RepoRoot "edge-agent\dist"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
Write-Host "  Cleaned build and dist directories."

# 3. Execute PyInstaller Build
Write-Host "`n[3/5] Compiling edge-agent distribution bundle..." -ForegroundColor Yellow
$SpecFile = Join-Path $RepoRoot "edge-agent\edge-ergo.spec"
$DistPath = Join-Path $RepoRoot "edge-agent\dist"
$WorkPath = Join-Path $RepoRoot "edge-agent\build"

pyinstaller $SpecFile --noconfirm --distpath $DistPath --workpath $WorkPath

$ExePath = Join-Path $RepoRoot "edge-agent\dist\edge-ergo\edge-ergo.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "PyInstaller completed but edge-ergo.exe was not produced at $ExePath"
    exit 1
}
Write-Host "  Executable successfully compiled at: $ExePath" -ForegroundColor Green

# 4. Inspect Distribution Bundle
Write-Host "`n[4/5] Running dist bundle safety and secret inspection..." -ForegroundColor Yellow
$InspectScript = Join-Path $RepoRoot "scripts\inspect_bundle.py"
$TargetDist = Join-Path $RepoRoot "edge-agent\dist\edge-ergo"
python $InspectScript --dist-dir $TargetDist
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dist bundle inspection failed."
    exit 1
}

# 5. Smoke Test Compiled Executable
Write-Host "`n[5/5] Running smoke execution tests against compiled executable..." -ForegroundColor Yellow

Write-Host "  Test A: --version flag" -ForegroundColor Cyan
& $ExePath --version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to execute 'edge-ergo.exe --version'"
    exit 1
}

Write-Host "  Test B: --selftest offline sanity verification" -ForegroundColor Cyan
& $ExePath --selftest
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to execute 'edge-ergo.exe --selftest'"
    exit 1
}

$FinalDist = Join-Path $RepoRoot "edge-agent\dist\edge-ergo"
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "BUILD SUCCESS: EdgeErgo Windows agent packaged and verified!" -ForegroundColor Green
Write-Host "Output Directory: $FinalDist" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
exit 0
