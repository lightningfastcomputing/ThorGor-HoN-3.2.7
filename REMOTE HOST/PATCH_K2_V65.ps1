param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
}

$target = Join-Path $HonHome 'k2.dll'
$candidate = Join-Path $HonHome 'k2.dll.thorgor_v65.new'
$builder = Join-Path $PSScriptRoot 'patches\build_k2_v65_state_delivery.py'
$v57Hash = '6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF'
$v65Hash = '82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB'

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
if (!(Test-Path -LiteralPath $target -PathType Leaf)) { throw "k2.dll not found: $target" }
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Patch builder not found: $builder" }

if ((Hash $target) -eq $v65Hash) {
    Write-Host 'K2 v65 linked-client state-block fix is already installed.' -ForegroundColor DarkGray
    exit 0
}

# Recreate the exact, verified v57 baseline from the preserved stock DLL first.
# This also rejects unsupported game versions and preserves the stock backup.
& (Join-Path $PSScriptRoot 'PATCH_K2_V57.ps1') -HonHome $HonHome
if ($LASTEXITCODE -ne 0) { throw 'K2 v57 baseline installation failed.' }
if ((Hash $target) -ne $v57Hash) { throw 'The verified K2 v57 baseline is unavailable.' }

try {
    $pythonExe = if ($env:THORGOR_PYTHON_EXE) { $env:THORGOR_PYTHON_EXE } else { & (Join-Path $PSScriptRoot 'FIND_PYTHON.ps1') }
    & $pythonExe $builder $target $candidate
    if ($LASTEXITCODE -ne 0) { throw 'K2 v65 patch builder failed.' }
    if ((Hash $candidate) -ne $v65Hash) { throw 'Generated K2 v65 hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}
Write-Host 'Generated and installed K2 v65 linked-client state-block delivery from the verified v57 baseline.' -ForegroundColor Green
