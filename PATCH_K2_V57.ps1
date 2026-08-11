param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    if (Test-Path -LiteralPath 'C:\intelprop\Heroes of Newerth\hon.exe') {
        $HonHome = 'C:\intelprop\Heroes of Newerth'
    } elseif (Test-Path -LiteralPath 'C:\Program Files (x86)\Heroes of Newerth\hon.exe') {
        $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
    } else {
        throw 'HoN installation not found. Pass -HonHome explicitly.'
    }
}

$target = Join-Path $HonHome 'k2.dll'
$backup = Join-Path $HonHome 'k2.dll.thorgor_stock_3.2.7.1'
$candidate = Join-Path $HonHome 'k2.dll.thorgor_v57.new'
$builder = Join-Path $PSScriptRoot 'patches\build_k2_v57.py'
$stockHash = '8929AE8993AF41AE9F63BEE43DAB27402205621CFFC57F8ACC8DB0C4FB95FAE9'
$v57Hash = '6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF'

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
if (!(Test-Path -LiteralPath $target -PathType Leaf)) { throw "k2.dll not found: $target" }
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Patch builder not found: $builder" }

$currentHash = Hash $target
if ($currentHash -eq $v57Hash) {
    Write-Host 'K2 v57 is already installed.' -ForegroundColor DarkGray
    exit 0
}
if ($currentHash -ne $stockHash) {
    throw "Expected an unmodified HoN 3.2.7.1 k2.dll. Got $currentHash"
}
if (!(Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $target -Destination $backup }
if ((Hash $backup) -ne $stockHash) { throw 'Verified stock K2 backup is unavailable.' }

try {
    & python $builder $backup $candidate
    if ($LASTEXITCODE -ne 0) { throw 'K2 patch builder failed.' }
    if ((Hash $candidate) -ne $v57Hash) { throw 'Generated K2 hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}
Write-Host 'Generated and installed K2 v57 from the verified user-supplied DLL.' -ForegroundColor Green
