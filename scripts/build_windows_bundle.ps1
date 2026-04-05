# Build vendor\python with Windows embeddable CPython + pip + requirements.txt
# Friends can then unzip your portable zip and run run.bat with zero install.
#
# Requires: Windows x64, PowerShell 5+, internet.
# Run from anywhere:  pwsh -File scripts\build_windows_bundle.ps1
# Optional:            pwsh -File scripts\build_windows_bundle.ps1 -PythonVersion 3.12.7

param(
    [string]$PythonVersion = "3.12.7"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Vendor = Join-Path $Root "vendor\python"

$Url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
Write-Host "==> Vibesort Windows bundle"
Write-Host "    Root:   $Root"
Write-Host "    Target: $Vendor"
Write-Host "    Python: $Url"
Write-Host ""

if (Test-Path $Vendor) {
    Write-Host "Removing existing vendor\python ..."
    Remove-Item -Recurse -Force $Vendor
}
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

$Zip = Join-Path $env:TEMP "py-embed-$PythonVersion-amd64.zip"
Write-Host "==> Downloading embeddable Python ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
Expand-Archive -Path $Zip -DestinationPath $Vendor -Force
Remove-Item $Zip -Force -ErrorAction SilentlyContinue

$Pth = Get-ChildItem -Path $Vendor -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) {
    throw "Could not find python*._pth in embeddable layout."
}
$pthContent = Get-Content $Pth.FullName -Raw
if ($pthContent -notmatch '(?m)^import site\s*$') {
    Add-Content -Path $Pth.FullName -Value "`r`nimport site"
    Write-Host "==> Appended 'import site' to $($Pth.Name)"
}

$Py = Join-Path $Vendor "python.exe"
$GetPip = Join-Path $Vendor "get-pip.py"
Write-Host "==> Bootstrapping pip ..."
& $Py -c @"
import urllib.request
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', r'$GetPip')
"@
& $Py $GetPip --no-warn-script-location
Remove-Item $GetPip -Force -ErrorAction SilentlyContinue

Write-Host "==> pip install -r requirements.txt (this may take several minutes) ..."
$Req = Join-Path $Root "requirements.txt"
& $Py -m pip install --upgrade pip setuptools wheel
& $Py -m pip install -r $Req --no-warn-script-location

Write-Host ""
Write-Host "==> Done."
Write-Host "    Test:  .\run.bat"
Write-Host "    Share: run  pwsh -File scripts\make_portable_zip.ps1  then send dist\Vibesort-Windows-portable.zip"
Write-Host ""
Write-Host "    Note: scikit-learn may need the MSVC runtime if pip used a binary wheel:"
Write-Host "    https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
Write-Host ""
