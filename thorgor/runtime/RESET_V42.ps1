$ErrorActionPreference = 'Stop'

$work = Join-Path $PSScriptRoot 'work'
$chat = Join-Path $PSScriptRoot 'chat-server'
New-Item -ItemType Directory -Path $work -Force | Out-Null

$workFiles = @(
    'manager_status_bridge_v42.log',
    'manager_status_bridge_v42_events.jsonl',
    'v42_manager_control.connected',
    'manager_status_bridge_v39.log',
    'v39_manager_control.connected',
    'hon_udp_shim_public_list.log',
    'v31_registration_state.json',
    'v31_registration_state.tmp',
    'v31_registration_state.bridge.tmp',
    'v31_registration_state.chat.tmp',
    'v42_run_id.txt'
)
foreach ($name in $workFiles) {
    Remove-Item -LiteralPath (Join-Path $work $name) -Force -ErrorAction SilentlyContinue
}

$workDirs = @(
    'manager_status_bridge_v42_captures',
    'manager_status_bridge_v39_captures'
)
foreach ($name in $workDirs) {
    Remove-Item -LiteralPath (Join-Path $work $name) -Recurse -Force -ErrorAction SilentlyContinue
}

foreach ($name in @('thorgor_srp_v39.log', 'thorgor_server_v39.log')) {
    Remove-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Force -ErrorAction SilentlyContinue
}
foreach ($name in @('thorgor_srp_v39_captures', 'thorgor_server_v39_captures')) {
    Remove-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Recurse -Force -ErrorAction SilentlyContinue
}

foreach ($name in @('thorgor_chat_v13.log', 'thorgor_chat_v13_host.log')) {
    Remove-Item -LiteralPath (Join-Path $chat $name) -Force -ErrorAction SilentlyContinue
}
foreach ($name in @('thorgor_chat_v13_captures', 'thorgor_chat_v13_host_captures')) {
    Remove-Item -LiteralPath (Join-Path $chat $name) -Recurse -Force -ErrorAction SilentlyContinue
}

$runId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N').Substring(0, 8))
Set-Content -LiteralPath (Join-Path $work 'v42_run_id.txt') -Value $runId -Encoding UTF8

Write-Host "v42 evidence state reset. Run ID: $runId" -ForegroundColor Green
