# MSIX Packaging Script for MixedBerryPie
# Usage: .\scripts\package_msix.ps1 [-Version "1.2.0"]
# If -Version is not specified, reads from pyproject.toml.
#
# Note: This script does NOT sign the package.
# - For Store submission: submit unsigned MSIX to Microsoft Partner Center.
# - For local testing: run .\scripts\sign_msix_local.ps1 after this script.

param(
    [string]$Version = ""
)

$ProjectRoot = Get-Item .
$PackageDir = Join-Path $ProjectRoot "package"
$AppFilesDir = Join-Path $PackageDir "app_files"
$OutputDir = Join-Path $ProjectRoot "dist"
$AppName = "MixedBerryPie"

# Resolve version
if (-not $Version) {
    $toml = Get-Content "pyproject.toml" -Raw
    if ($toml -match 'version\s*=\s*"([^"]+)"') {
        $Version = $matches[1]
    } else {
        Write-Error "Could not determine version from pyproject.toml"
        exit 1
    }
}
Write-Host "==> Packaging MSIX version: $Version" -ForegroundColor Cyan

$MSIXName = "${AppName}_v${Version}.msix"
$MSIXPath = Join-Path $OutputDir $MSIXName

# 1. Verify the executable exists
if (-not (Test-Path "$OutputDir\$AppName.exe")) {
    Write-Error "Executable not found at $OutputDir\$AppName.exe. Run the build step first."
    exit 1
}

# 2. Prepare Package Directory
Write-Host "==> Preparing Package Directory..." -ForegroundColor Cyan
if (Test-Path $AppFilesDir) { Remove-Item -Recurse -Force $AppFilesDir }
New-Item -ItemType Directory -Path $AppFilesDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $AppFilesDir "Assets") -Force | Out-Null

# Copy files
Copy-Item "$OutputDir\$AppName.exe" "$AppFilesDir\"
Copy-Item -Recurse "resources" "$AppFilesDir\"
if (Test-Path "package\assets") {
    Copy-Item "package\assets\*" "$AppFilesDir\Assets\" -ErrorAction SilentlyContinue
}
Copy-Item "package\AppxManifest.xml" "$AppFilesDir\"

# 3. Create MSIX Package
Write-Host "==> Creating MSIX Package..." -ForegroundColor Cyan
$MakeAppx = "MakeAppx.exe"
Get-Command $MakeAppx -ErrorAction SilentlyContinue | Out-Null
if (-not $?) {
    $sdkPaths = @(
        "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe",
        "C:\Program Files (x86)\Windows Kits\10\bin\*\x86\makeappx.exe"
    )
    foreach ($pathPattern in $sdkPaths) {
        $found = Resolve-Path $pathPattern -ErrorAction SilentlyContinue | Sort-Object -Descending | Select-Object -First 1
        if ($found) {
            $MakeAppx = $found.Path
            break
        }
    }
}

if (-not (Test-Path $MakeAppx)) {
    Write-Error "MakeAppx.exe not found. Please install Windows SDK."
    exit 1
}

& $MakeAppx pack /d $AppFilesDir /p $MSIXPath /o
if ($LASTEXITCODE -ne 0) {
    Write-Error "MakeAppx failed with exit code $LASTEXITCODE"
    exit 1
}

Write-Host "[OK] MSIX package created (unsigned): $MSIXPath" -ForegroundColor Green
Write-Host "  -> For Store submission: upload this file to Microsoft Partner Center." -ForegroundColor DarkGray
Write-Host "  -> For local testing: run .\scripts\sign_msix_local.ps1" -ForegroundColor DarkGray
