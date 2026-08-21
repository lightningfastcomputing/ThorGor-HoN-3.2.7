param([Parameter(Mandatory = $true)][string]$HonHome)
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'PATCH_K2_V76.ps1') -HonHome $HonHome
& (Join-Path $PSScriptRoot 'PATCH_CGAME_V61.ps1') -HonHome $HonHome

Write-Host 'ThorGor K2 v76 and cgame v61 are installed and hash-verified.' -ForegroundColor Green
