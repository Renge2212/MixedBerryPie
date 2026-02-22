# install_cert.ps1
# This script installs the local test certificate for MixedBerryPie
# It requires Administrator privileges and will prompt for UAC if needed.

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "エラー: 管理者権限がありません。" -ForegroundColor Red
    Write-Host "このスクリプトは、スタートメニューから「PowerShell（管理者）」を開いて実行してください。" -ForegroundColor Yellow
    Read-Host "Enterキーを押して終了します"
    exit
}

$CertFile = Join-Path (Split-Path $PSScriptRoot -Parent) "package\LocalTestCert.pfx"
if (-not (Test-Path $CertFile -PathType Leaf)) {
    Write-Host "エラー: 証明書が見つかりません: $CertFile" -ForegroundColor Red
    Read-Host "Enterキーを押して終了します"
    exit
}

$password = ConvertTo-SecureString -String "1234" -Force -AsPlainText
Import-PfxCertificate -FilePath $CertFile -CertStoreLocation Cert:\LocalMachine\Root -Password $password | Out-Null
Write-Host "完了: 証明書をインストールしました！" -ForegroundColor Green
Read-Host "Enterキーを押して終了します"


