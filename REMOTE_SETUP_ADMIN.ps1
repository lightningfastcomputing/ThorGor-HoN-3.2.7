param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [Parameter(Mandatory = $true)][string]$HonHome,
    [Parameter(Mandatory = $true)][string]$ServerIP,
    [Parameter(Mandatory = $true)][string]$LogPath
)

$ErrorActionPreference = 'Stop'
$log = $LogPath

try {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "Python executable is unavailable: $PythonPath"
    }
    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        throw "ThorGor project directory is unavailable: $ProjectRoot"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $HonHome 'hon.exe') -PathType Leaf)) {
        throw "HoN installation is unavailable: $HonHome"
    }

    Set-Location -LiteralPath $ProjectRoot
    $output = @(& $PythonPath -m thorgor remote-setup --hon-home $HonHome --server-ip $ServerIP 2>&1)
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }

    if ($exitCode -ne 0) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null
        $output | Out-File -LiteralPath $log -Encoding utf8
        exit $(if ($exitCode) { $exitCode } else { 1 })
    }

    Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
    exit 0
}
catch {
    New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null
    ($_ | Out-String) | Set-Content -LiteralPath $log -Encoding utf8
    Write-Host $_ -ForegroundColor Red
    exit 1
}
