param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [Parameter(Mandatory = $true)][string]$HonHome,
    [Parameter(Mandatory = $true)][string]$ServerIP,
    [Parameter(Mandatory = $true)][string]$LogPath,
    [ValidateSet('v39', 'registry-continuity', 'selection-recovery')]
    [string]$NativeVariant = 'selection-recovery'
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

    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', ('"{0}"' -f $PSCommandPath),
            '-PythonPath', ('"{0}"' -f $PythonPath),
            '-ProjectRoot', ('"{0}"' -f $ProjectRoot),
            '-HonHome', ('"{0}"' -f $HonHome),
            '-ServerIP', $ServerIP,
            '-LogPath', ('"{0}"' -f $LogPath),
            '-NativeVariant', $NativeVariant
        )
        $elevated = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList $arguments
        exit $elevated.ExitCode
    }

    Set-Location -LiteralPath $ProjectRoot
    $env:THORGOR_NATIVE_VARIANT = $NativeVariant
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
