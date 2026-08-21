param([string]$HonHome = $env:THORGOR_HON_HOME)
$ErrorActionPreference = 'Stop'

$required = @(
    'thorgor_hon_sandboxed_masterserver_v39.py',
    'chat-server\thorgor_hon_chatserver_v13.py',
    'hon_udp_shim.py',
    'hon_manager_status_bridge_v42.py',
    'hon_native_matchid_bridge_v47.py',
    'patches\build_k2_v57.py',
    'patches\build_k2_v77_tail_recipient_hero_fix.py',
    'patches\build_cgame_v61_complete_registry_guard.py'
)
foreach ($relative in $required) {
    $path = Join-Path $PSScriptRoot $relative
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing required source file: $relative" }
}

if ($HonHome) {
    $expected = @{
        (Join-Path $HonHome 'k2.dll') = '25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026'
        (Join-Path $HonHome 'game\cgame.dll') = '88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988'
    }
    foreach ($path in $expected.Keys) {
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing installed file: $path" }
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($hash -ne $expected[$path]) { throw "Installed file hash mismatch: $path" }
    }
}

Write-Host 'ThorGor source and installed-patch checks passed.' -ForegroundColor Green
