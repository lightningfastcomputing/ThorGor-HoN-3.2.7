param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
}

$target = Join-Path $HonHome 'k2.dll'
$candidate = Join-Path $HonHome 'k2.dll.thorgor_v76.new'
$backup = Join-Path $HonHome 'k2.dll.thorgor_before_v76'
$v65Backup = Join-Path $HonHome 'k2.dll.thorgor_v65_before_v75'
$builder = Join-Path $PSScriptRoot 'patches\build_k2_v76_world_ready_hero_state_reconciliation.py'
$v65Hash = '82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB'
$v75Hash = '9D731944738C6CA014CB71F25F82DCE8634522247AB935513E2F5A0889C0BFF3'
$v76Hash = 'FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0'

function Hash([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

if (!(Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "k2.dll not found: $target"
}
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) {
    throw "Patch builder not found: $builder"
}

$currentHash = Hash $target
if ($currentHash -eq $v76Hash) {
    Write-Host 'K2 v76 world-ready hero-state reconciliation is already installed.' -ForegroundColor DarkGray
    return
}
$source = $target
if ($currentHash -eq $v75Hash) {
    if (!(Test-Path -LiteralPath $v65Backup -PathType Leaf) -or (Hash $v65Backup) -ne $v65Hash) {
        throw "K2 v75 is installed, but its verified v65 backup is missing: $v65Backup"
    }
    $source = $v65Backup
} elseif ($currentHash -ne $v65Hash) {
    throw "K2 v76 requires verified v65 or v75. Current hash: $currentHash"
}

Copy-Item -LiteralPath $target -Destination $backup -Force

try {
    $pythonExe = if ($env:THORGOR_PYTHON_EXE) {
        $env:THORGOR_PYTHON_EXE
    } else {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'FIND_PYTHON.ps1')
    }
    if (-not $pythonExe) { throw 'Python was not found.' }
    & $pythonExe $builder $source $candidate
    if ($LASTEXITCODE -ne 0) { throw 'K2 v76 patch builder failed.' }
    if ((Hash $candidate) -ne $v76Hash) { throw 'Generated K2 v76 hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}

Write-Host 'Installed K2 v76 world-ready reconciliation for hero blocks 3 through 8.' -ForegroundColor Green
