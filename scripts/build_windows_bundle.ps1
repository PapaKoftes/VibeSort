# Requires PowerShell. Downloads embeddable Python into vendor/python and pip-installs requirements.
# Edit $PyVersion / $PyTag to match a current release from python.org.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Vendor = Join-Path $Root "vendor\python"
$PyVersion = "3.12.8"
$PyTag = "312"   # embeddable zip uses python312.zip style

$Url = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
Write-Host "Downloading $Url ..."
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
$Zip = Join-Path $env:TEMP "py-embed-$PyTag.zip"
Invoke-WebRequest -Uri $Url -OutFile $Zip
Expand-Archive -Path $Zip -DestinationPath $Vendor -Force

$Pth = Get-ChildItem -Path $Vendor -Filter "python*._pth" | Select-Object -First 1
if ($Pth) {
    $lines = Get-Content $Pth.FullName
    if ($lines -notcontains "import site") {
        Add-Content $Pth.FullName "import site"
        Write-Host "Enabled import site in $($Pth.Name)"
    }
}

$Py = Join-Path $Vendor "python.exe"
Write-Host "Bootstrapping pip (see https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) ..."
& $Py -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', r'$Vendor\get-pip.py')"
& $Py (Join-Path $Vendor "get-pip.py") --no-warn-script-location

$Req = Join-Path $Root "requirements.txt"
& $Py -m pip install -r $Req
Write-Host "Done. Run from repo root: .\run.bat"
