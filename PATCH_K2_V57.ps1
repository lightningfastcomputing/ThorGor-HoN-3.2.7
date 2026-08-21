param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
}

$target = Join-Path $HonHome 'k2.dll'
$backup = Join-Path $HonHome 'k2.dll.thorgor_stock_3.2.7.1'
$candidate = Join-Path $HonHome 'k2.dll.thorgor_v57.new'
$builder = Join-Path $PSScriptRoot 'patches\build_k2_v57.py'
$cleanStockHash = '04AA0DBCC88A86AD8D7C5429A24CE79A62DBB8C40B552AC629D0D76079254095'
$sandboxedStockHash = '8929AE8993AF41AE9F63BEE43DAB27402205621CFFC57F8ACC8DB0C4FB95FAE9'
$stockHashes = @($cleanStockHash, $sandboxedStockHash)
$v57Hash = '6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF'

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
if (!(Test-Path -LiteralPath $target -PathType Leaf)) { throw "k2.dll not found: $target" }
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Patch builder not found: $builder" }

$currentHash = Hash $target
if ($currentHash -eq $v57Hash) {
    Write-Host 'K2 v57 is already installed.' -ForegroundColor DarkGray
    return
}

$verifiedBackup = (Test-Path -LiteralPath $backup -PathType Leaf) -and ($stockHashes -contains (Hash $backup))
if ($stockHashes -contains $currentHash) {
    if (Test-Path -LiteralPath $backup -PathType Leaf) {
        if (-not $verifiedBackup) { throw "The existing K2 backup is not stock HoN 3.2.7.1: $backup" }
    } else {
        Copy-Item -LiteralPath $target -Destination $backup
        $verifiedBackup = $true
    }
} elseif ($verifiedBackup) {
    Write-Host "Current k2.dll is unrecognized ($currentHash); recovering from the verified stock backup." -ForegroundColor Yellow
} else {
    throw "Unsupported k2.dll ($currentHash). Restore genuine HoN 3.2.7.1 k2.dll (SHA-256 $cleanStockHash), or restore a verified copy at $backup."
}
if ($stockHashes -notcontains (Hash $backup)) { throw 'Verified stock K2 backup is unavailable.' }

try {
    $pythonExe = if ($env:THORGOR_PYTHON_EXE) { $env:THORGOR_PYTHON_EXE } else { & (Join-Path $PSScriptRoot 'FIND_PYTHON.ps1') }
    & $pythonExe $builder $backup $candidate
    if ($LASTEXITCODE -ne 0) { throw 'K2 patch builder failed.' }
    if ((Hash $candidate) -ne $v57Hash) { throw 'Generated K2 hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}
Write-Host 'Generated and installed K2 v57 from the verified user-supplied DLL.' -ForegroundColor Green
