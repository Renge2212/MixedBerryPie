# MSIX Packaging Script for MixedBerryPie

$ProjectRoot = Get-Item .
$PackageDir = Join-Path $ProjectRoot "package"
$AppFilesDir = Join-Path $PackageDir "app_files"
$OutputDir = Join-Path $ProjectRoot "dist"
$AppName = "MixedBerryPie"

Write-Host "==> 1. Building Executable..." -ForegroundColor Cyan
uv run scripts/build.py

if (-not (Test-Path "$OutputDir\$AppName.exe")) {
    Write-Error "Build failed! Executable not found."
    exit 1
}

Write-Host "==> 2. Preparing Package Directory..." -ForegroundColor Cyan
if (Test-Path $AppFilesDir) { Remove-Item -Recurulse -Force $AppFilesDir }
New-Item -ItemType Directory -Path $AppFilesDir -Force
New-Item -ItemType Directory -Path (Join-Path $AppFilesDir "Assets") -Force

# Copy Files
Copy-Item "$OutputDir\$AppName.exe" "$AppFilesDir\"
Copy-Item -Recurse "resources" "$AppFilesDir\"
Copy-Item "package\assets\*" "$AppFilesDir\Assets\"
Copy-Item "package\AppxManifest.xml" "$AppFilesDir\"

Write-Host "==> 3. Creating MSIX Package..." -ForegroundColor Cyan
# Locate MakeAppx.exe
$MakeAppx = "MakeAppx.exe"
Get-Command $MakeAppx -ErrorAction SilentlyContinue | Out-Null
if (-not $?) {
    # Search common Windows SDK paths
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

if ($MakeAppx -and (Test-Path $MakeAppx)) {
    $MSIXPath = Join-Path $OutputDir "$AppName.msix"
    Write-Host "Using MakeAppx: $MakeAppx" -ForegroundColor Gray
    & $MakeAppx pack /d $AppFilesDir /p $MSIXPath /o
    Write-Host "[OK] MSIX package created: $MSIXPath" -ForegroundColor Green
} else {
    Write-Warning "MakeAppx.exe not found. Please install Windows SDK or run this from a Developer Command Prompt."
    Write-Host "Package files are ready in: $AppFilesDir" -ForegroundColor Yellow
}

Write-Host "`nPreparation Complete!" -ForegroundColor Green
