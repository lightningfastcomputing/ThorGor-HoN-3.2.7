param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
}

$target = Join-Path $HonHome 'game\cgame.dll'
$backup = Join-Path $HonHome 'game\cgame.dll.thorgor_stock_3.2.7.1'
$candidate = Join-Path $HonHome 'game\cgame.dll.thorgor_v61.new'
$builder = Join-Path $PSScriptRoot 'patches\build_cgame_v61_complete_registry_guard.py'
$stockHash = '45B3CE39214EFD82D12DA8B01E73494CEE983D6DB4891C7D95DF10B2EAA70B02'
$v61Hash = '88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988'

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
if (!(Test-Path -LiteralPath $target -PathType Leaf)) { throw "cgame.dll not found: $target" }
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Patch builder not found: $builder" }

$currentHash = Hash $target
if ($currentHash -eq $v61Hash) {
    Write-Host 'cgame v61 is already installed.' -ForegroundColor DarkGray
    return
}

$verifiedBackup = (Test-Path -LiteralPath $backup -PathType Leaf) -and ((Hash $backup) -eq $stockHash)
if ($currentHash -eq $stockHash) {
    if (Test-Path -LiteralPath $backup -PathType Leaf) {
        if (-not $verifiedBackup) { throw "The existing cgame backup is not stock HoN 3.2.7.1: $backup" }
    } else {
        Copy-Item -LiteralPath $target -Destination $backup
        $verifiedBackup = $true
    }
} elseif ($verifiedBackup) {
    Write-Host "Current cgame.dll is unrecognized ($currentHash); recovering from the verified stock backup." -ForegroundColor Yellow
} else {
    throw "Unsupported cgame.dll ($currentHash). Restore stock HoN 3.2.7.1 cgame.dll (SHA-256 $stockHash), or restore a verified copy at $backup."
}
if ((Hash $backup) -ne $stockHash) { throw 'Verified stock cgame backup is unavailable.' }

try {
    $pythonExe = if ($env:THORGOR_PYTHON_EXE) { $env:THORGOR_PYTHON_EXE } else { & (Join-Path $PSScriptRoot 'FIND_PYTHON.ps1') }
    & $pythonExe $builder $backup $candidate
    if ($LASTEXITCODE -ne 0) { throw 'cgame patch builder failed.' }
    if ((Hash $candidate) -ne $v61Hash) { throw 'Generated cgame hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}
Write-Host 'Generated and installed cgame v61 from the verified user-supplied DLL.' -ForegroundColor Green
