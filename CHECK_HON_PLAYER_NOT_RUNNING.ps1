param([string[]]$CommandLines)
$ErrorActionPreference = 'Stop'

if ($PSBoundParameters.ContainsKey('CommandLines')) {
    $honProcesses = @($CommandLines | ForEach-Object {
        [pscustomobject]@{ ProcessId = 0; CommandLine = $_ }
    })
} else {
    $honProcesses = @(Get-CimInstance Win32_Process -Filter "Name='hon.exe'")
}

$serverMode = '(?i)(?:^|\s)-(?:manager|dedicated)(?:\s|$)'
$players = @($honProcesses | Where-Object {
    -not $_.CommandLine -or $_.CommandLine -notmatch $serverMode
})

if ($players.Count) {
    Write-Host '[STOP] A HoN player client is already running on this PC.' -ForegroundColor Red
    foreach ($player in $players) {
        Write-Host "  PID $($player.ProcessId): $($player.CommandLine)"
    }
    exit 7
}

$serverCount = @($honProcesses | Where-Object { $_.CommandLine -match $serverMode }).Count
if ($serverCount) {
    Write-Host "[OK] Ignoring $serverCount HoN manager/dedicated server process(es)." -ForegroundColor Green
}
exit 0
