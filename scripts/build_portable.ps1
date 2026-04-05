# One-shot: embeddable Python + deps + portable zip into dist\
#
#   pwsh -File scripts\build_portable.ps1
#
# Output: dist\Vibesort-Windows-portable.zip  (share this; not committed to git)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Here "build_windows_bundle.ps1")
& (Join-Path $Here "make_portable_zip.ps1")
