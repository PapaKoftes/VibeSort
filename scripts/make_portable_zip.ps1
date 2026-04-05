# Create dist\Vibesort-Windows-portable.zip for sharing (includes vendor\python).
# Run AFTER scripts\build_windows_bundle.ps1
#
#   pwsh -File scripts\make_portable_zip.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VendorPy = Join-Path $Root "vendor\python\python.exe"

if (-not (Test-Path $VendorPy)) {
    Write-Error "vendor\python\python.exe not found. Run first: pwsh -File scripts\build_windows_bundle.ps1"
}

$Dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$OutZip = Join-Path $Dist "Vibesort-Windows-portable.zip"
if (Test-Path $OutZip) {
    Remove-Item $OutZip -Force
}

$TmpZip = Join-Path $env:TEMP "Vibesort-portable-$([Guid]::NewGuid().ToString('N').Substring(0, 10)).zip"

Write-Host "==> Archiving (excluding .git, caches, outputs, .env) ..."
Set-Location $Root
# Zip is written outside the tree first to avoid tar reading the open archive.
tar.exe -a -c -f $TmpZip `
    --exclude=.git `
    --exclude=outputs `
    --exclude=.env `
    --exclude=__pycache__ `
    --exclude=.pytest_cache `
    --exclude=.cursor `
    --exclude=dist `
    --exclude=*.pyc `
    .

Move-Item -Force $TmpZip $OutZip
Write-Host "==> Wrote $OutZip"
$sizeMb = [math]::Round((Get-Item $OutZip).Length / 1MB, 1)
Write-Host "    Size: ~$sizeMb MB"
Write-Host ""
Write-Host "Send that zip to friends. They unzip and double-click run.bat"
Write-Host ""
