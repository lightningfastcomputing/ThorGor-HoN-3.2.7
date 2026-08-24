param([string]$HonHome = "")
$ErrorActionPreference = 'Stop'

if (-not $HonHome) {
    $HonHome = 'C:\Program Files (x86)\Heroes of Newerth'
}

$target = Join-Path $HonHome 'k2.dll'
$candidate = Join-Path $HonHome 'k2.dll.thorgor_v77.new'
$backup = Join-Path $HonHome 'k2.dll.thorgor_before_v77'
$v65Backup = Join-Path $HonHome 'k2.dll.thorgor_v65_before_v75'
$builder = Join-Path $PSScriptRoot 'patches\build_k2_v77_tail_recipient_hero_fix.py'
$v65Hash = '82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB'
$v75Hash = '9D731944738C6CA014CB71F25F82DCE8634522247AB935513E2F5A0889C0BFF3'
$v76Hash = 'FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0'
$v77Hash = '25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026'

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
if ($currentHash -eq $v77Hash) {
    Write-Host 'K2 v77 tail-recipient hero-state fix is already installed.' -ForegroundColor DarkGray
    return
}
$source = $target
if ($currentHash -eq $v75Hash -or $currentHash -eq $v76Hash) {
    if (!(Test-Path -LiteralPath $v65Backup -PathType Leaf) -or (Hash $v65Backup) -ne $v65Hash) {
        throw "K2 v75/v76 is installed, but its verified v65 backup is missing: $v65Backup"
    }
    $source = $v65Backup
} elseif ($currentHash -ne $v65Hash) {
    Write-Host "K2 v77 requires the verified v65 baseline; preparing it from the current verified installation ($currentHash)." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot 'PATCH_K2_V65.ps1') -HonHome $HonHome
    $currentHash = Hash $target
    if ($currentHash -ne $v65Hash) {
        throw "K2 v65 baseline preparation failed. Current hash: $currentHash"
    }
    $source = $target
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
    if ($LASTEXITCODE -ne 0) { throw 'K2 v77 patch builder failed.' }
    if ((Hash $candidate) -ne $v77Hash) { throw 'Generated K2 v77 hash verification failed.' }
    Move-Item -LiteralPath $candidate -Destination $target -Force
} finally {
    Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
}

Write-Host 'Installed K2 v77 tail-recipient delivery for hero blocks 3 through 8.' -ForegroundColor Green
