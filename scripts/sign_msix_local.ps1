# Local Signing Script for MixedBerryPie MSIX
# Note: This is only for local testing. The Microsoft Store will handle final signing.

$PublisherID = "CN=AC64A0E6-FC09-4DAC-A8B8-13B770643707"
$CertFile = "package\LocalTestCert.pfx"

# Find the latest MSIX file in the dist folder
$MSIXPath = Get-ChildItem "dist\MixedBerryPie_v*.msix" | Sort-Object LastWriteTime -Descending | Select-Object -ExpandProperty FullName -First 1

if (-not $MSIXPath) {
    $MSIXPath = "dist\MixedBerryPie.msix"
}

# 1. Find SignTool
$SignTool = "signtool.exe"
Get-Command $SignTool -ErrorAction SilentlyContinue | Out-Null
if (-not $?) {
    $sdkPaths = @(
        "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
        "C:\Program Files (x86)\Windows Kits\10\bin\*\x86\signtool.exe"
    )
    foreach ($pathPattern in $sdkPaths) {
        $found = Resolve-Path $pathPattern -ErrorAction SilentlyContinue | Sort-Object -Descending | Select-Object -First 1
        if ($found) {
            $SignTool = $found.Path
            break
        }
    }
}

if (-not (Test-Path $SignTool)) {
    Write-Error "SignTool.exe not found. Please ensure Windows SDK is installed."
    exit 1
}

# 2. Create Self-Signed certificate (Overwrite existing)
if (Test-Path $CertFile) { Remove-Item $CertFile }

Write-Host "==> Creating Self-Signed Certificate..." -ForegroundColor Cyan
$cert = New-SelfSignedCertificate -Type Custom -Subject $PublisherID -KeyUsage DigitalSignature -FriendlyName "MixedBerryPie Local Test" -CertStoreLocation "Cert:\CurrentUser\My" -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")

$passwordStr = "1234"
$password = ConvertTo-SecureString -String $passwordStr -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $CertFile -Password $password
Write-Host "[OK] Certificate created: $CertFile (Password: $passwordStr)" -ForegroundColor Green

# 3. Sign the MSIX
if (Test-Path $MSIXPath) {
    Write-Host "==> Signing MSIX Package..." -ForegroundColor Cyan
    & $SignTool sign /fd SHA256 /a /f $CertFile /p "1234" $MSIXPath
    Write-Host "[OK] MSIX package signed!" -ForegroundColor Green
} else {
    Write-Error "MSIX file not found at $MSIXPath. Run package_msix.ps1 first."
}
