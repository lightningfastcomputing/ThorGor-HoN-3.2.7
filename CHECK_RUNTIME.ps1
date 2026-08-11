param([string]$HonHome = $env:THORGOR_HON_HOME)
$ErrorActionPreference = 'Stop'

$required = @(
    'thorgor_hon_sandboxed_masterserver_v39.py',
    'chat-server\thorgor_hon_chatserver_v13.py',
    'hon_udp_shim.py',
    'hon_manager_status_bridge_v42.py',
    'hon_native_matchid_bridge_v47.py',
    'patches\build_k2_v57.py',
    'patches\build_cgame_v61_complete_registry_guard.py'
)
foreach ($relative in $required) {
    $path = Join-Path $PSScriptRoot $relative
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing required source file: $relative" }
}

if ($HonHome) {
    $expected = @{
        (Join-Path $HonHome 'k2.dll') = '6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF'
        (Join-Path $HonHome 'game\cgame.dll') = '88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988'
    }
    foreach ($path in $expected.Keys) {
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing installed file: $path" }
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($hash -ne $expected[$path]) { throw "Installed file hash mismatch: $path" }
    }
}

Write-Host 'ThorGor source and installed-patch checks passed.' -ForegroundColor Green
