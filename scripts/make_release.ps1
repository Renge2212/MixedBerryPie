# make_release.ps1
# Automates the build and installer creation process for Pie Menu.

# Fix encoding issues for emoji and special characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# --- Configuration ---
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$BuildScript = "$ProjectRoot\scripts\build.py"
$IssScript = "$ProjectRoot\MixedBerryPie.iss"

# Path to Inno Setup Compiler - Search in standard locations and PATH
$ISCC = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($ISCC) {
    $ISCC = $ISCC.Source
} else {
    $CommonPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    )
    foreach ($Path in $CommonPaths) {
        if (Test-Path $Path) {
            $ISCC = $Path
            break
        }
    }
}

# Application name will be set in the try block after checking Python
$AppName = $null
$ExeName = $null
$DistExe = $null
$OutputInstaller = $null

# --- Functions ---

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

# --- Main Execution ---

try {
    # 1. Check prerequisites
    Write-Step "Checking prerequisites..."
    
    if (-not $ISCC -or -not (Test-Path $ISCC)) {
        throw "Inno Setup Compiler (ISCC.exe) not found.`nPlease install Inno Setup 6 and ensure it is in your PATH or standard installation directory."
    }
    
    # Check for uv or python
    if (Get-Command "uv" -ErrorAction SilentlyContinue) {
        $PythonCmd = @("uv", "run", "python")
        $PythonCmdStr = "uv run python"
    } elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
        $PythonCmd = @("python")
        $PythonCmdStr = "python"
    } else {
        throw "Neither 'uv' nor 'python' found in PATH. Please install Python."
    }
    Write-Success "Prerequisites check passed. Using: $PythonCmdStr"
    
    # Get application name from config_reader.py
    $PythonCode = @"
import sys
sys.path.insert(0, r'$ProjectRoot')
from scripts.config_reader import get_app_display_name
print(get_app_display_name())
"@
    # Execute Python code using the same command as for building
    if ($PythonCmd.Count -eq 3) {
        $AppName = & $PythonCmd[0] $PythonCmd[1] $PythonCmd[2] -c $PythonCode
    } elseif ($PythonCmd.Count -eq 1) {
        $AppName = & $PythonCmd[0] -c $PythonCode
    } else {
        throw "Unexpected Python command format"
    }
    $ExeName = "$AppName.exe"
    $DistExe = "$ProjectRoot\dist\$ExeName"
    $OutputInstaller = "$ProjectRoot\Output\${AppName}_Setup_v*.exe"
    Write-Host "Application name: $AppName"

    # 2. Run Python Build Script
    Write-Step "Building executable with PyInstaller..."
    
    $BuildProcess = Start-Process -FilePath "powershell" -ArgumentList "-Command $PythonCmdStr $BuildScript" -Wait -PassThru -NoNewWindow
    
    if ($BuildProcess.ExitCode -ne 0) {
        throw "Build script failed with exit code $($BuildProcess.ExitCode)."
    }
    
    if (-not (Test-Path $DistExe)) {
        throw "Build finished but $DistExe was not found."
    }
    Write-Success "Executable built successfully."

    # 3. Create Installer with Inno Setup
    Write-Step "Creating installer with Inno Setup..."
    
    $IsccProcess = Start-Process -FilePath $ISCC -ArgumentList "`"$IssScript`"" -Wait -PassThru -NoNewWindow
    
    if ($IsccProcess.ExitCode -ne 0) {
        throw "Inno Setup compilation failed with exit code $($IsccProcess.ExitCode)."
    }
    
    # 4. Verify Output
    $Installer = Get-ChildItem "$ProjectRoot\Output\${AppName}_Setup_v*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    
    if ($Installer) {
        Write-Success "Installer created successfully!"
        Write-Host "-> Location: $($Installer.FullName)"
    } else {
        throw "Installer compilation finished, but no output file was found."
    }

} catch {
    Write-ErrorMsg "Process failed: $_"
    exit 1
}

Write-Host "`n*** Release process completed successfully!"
exit 0
