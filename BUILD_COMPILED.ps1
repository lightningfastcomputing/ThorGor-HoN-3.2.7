[CmdletBinding()]
param([string]$PythonExe = '')

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$buildRoot = Join-Path $root 'build\pyinstaller'
$specRoot = Join-Path $root 'build\specs'

if (-not $PythonExe) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { $PythonExe = $pythonCommand.Source }
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw 'Python was not found. Pass -PythonExe with a Python 3.10+ executable.'
}

New-Item -ItemType Directory -Force -Path $buildRoot, $specRoot | Out-Null

$targets = @(
    @{ Name = 'ThorGorMasterServer'; Script = 'thorgor_hon_sandboxed_masterserver_v39.py'; Windowed = $false },
    @{ Name = 'ThorGorChatServer'; Script = 'chat-server\thorgor_hon_chatserver_v13.py'; Windowed = $false },
    @{ Name = 'ThorGorUdpShim'; Script = 'hon_udp_shim.py'; Windowed = $false },
    @{ Name = 'ThorGorManagerBridge'; Script = 'hon_manager_status_bridge_v42.py'; Windowed = $false },
    @{ Name = 'ThorGorNativeBridge'; Script = 'hon_native_matchid_bridge_v47.py'; Windowed = $false },
    @{ Name = 'ThorGorAccountManager'; Script = 'manage_accounts_v43.py'; Windowed = $false },
    @{ Name = 'ThorGorDashboard'; Script = 'hon_v49_dashboard.py'; Windowed = $true }
)

foreach ($target in $targets) {
    Write-Host "Building $($target.Name)..." -ForegroundColor Cyan
    $arguments = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
        '--name', $target.Name,
        '--distpath', $root,
        '--workpath', $buildRoot,
        '--specpath', $specRoot
    )
    $arguments += if ($target.Windowed) { '--windowed' } else { '--console' }
    $arguments += Join-Path $root $target.Script
    & $PythonExe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed for $($target.Name)."
    }
}

Write-Host 'Compiled ThorGor distribution is ready.' -ForegroundColor Green
Get-ChildItem -LiteralPath $root -Filter 'ThorGor*.exe' | Select-Object Name, Length
