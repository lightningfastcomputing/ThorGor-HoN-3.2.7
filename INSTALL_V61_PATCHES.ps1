param([Parameter(Mandatory = $true)][string]$HonHome)
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'PATCH_K2_V57.ps1') -HonHome $HonHome
& (Join-Path $PSScriptRoot 'PATCH_CGAME_V61.ps1') -HonHome $HonHome

Write-Host 'ThorGor v61 patches were generated from and installed over verified user-supplied files.' -ForegroundColor Green
