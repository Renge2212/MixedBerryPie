# setup.ps1
# Automated development environment setup for MixedBerryPie.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host -ForegroundColor Cyan "`n==> $Message"
}

function Write-Success {
    param([string]$Message)
    Write-Host -ForegroundColor Green "[OK] $Message"
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host -ForegroundColor Red "[ERROR] $Message"
}

try {
    Write-Step "Checking prerequisites..."

    # 1. Check for uv
    if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg " 'uv' (package manager) not found."
        Write-Host "Please install uv: https://github.com/astral-sh/uv"
        exit 1
    }
    Write-Success "Found 'uv'."

    # 2. Sync dependencies
    Write-Step "Synchronizing dependencies (uv sync)..."
    uv sync
    Write-Success "Dependencies synchronized."

    # 3. Install pre-commit hooks
    if (Test-Path ".pre-commit-config.yaml") {
        Write-Step "Installing pre-commit hooks..."
        uv run pre-commit install
        Write-Success "Pre-commit hooks installed."
    }

    # 4. Basic verification
    Write-Step "Running basic verification..."
    uv run python scripts/verify_ui_imports.py
    Write-Success "Verification passed."

    Write-Host "`n*** Setup completed successfully!"
    Write-Host "You can now run the app with: uv run run.py"
    Write-Host "Or run tests with: ./run_tests.ps1"

} catch {
    Write-ErrorMsg "Setup failed: $_"
    exit 1
}
