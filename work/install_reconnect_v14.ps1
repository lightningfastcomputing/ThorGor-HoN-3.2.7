$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
        -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    exit $process.ExitCode
}

$repository = 'C:\Users\Thor\Documents\Codex\2026-09-07\https-github-com-lightningfastcomputing-thorgor-hon-2\ThorGor-HoN-3.2.7'
$gameDirectory = 'C:\Program Files (x86)\Heroes of Newerth'
$expectedK2 = 'B0CFEA2ACE1EAF7D7F8CE66C4D8750775A2A18AE22521C47C94EA5A6B4CA375E'
$expectedGame = '614EA87B07858531A6F741CB33ED8B9922F5A7D9EA8EE1DC40351437C3A1C01A'
$env:PYTHONPATH = $repository
$log = Join-Path $repository 'work\install_reconnect_v14.log'

try {
    $ErrorActionPreference = 'Continue'
    $output = & 'C:\Python314\python.exe' -c "from pathlib import Path; from patches.installer import install_game_capacity, install_k2; p=Path(r'$gameDirectory'); print(install_game_capacity(p)); print(install_k2(p))" 2>&1
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        throw ($output | Out-String)
    }
    $actualK2 = (Get-FileHash -LiteralPath (Join-Path $gameDirectory 'k2.dll') -Algorithm SHA256).Hash
    $actualGame = (Get-FileHash -LiteralPath (Join-Path $gameDirectory 'game\game.dll') -Algorithm SHA256).Hash
    if ($actualK2 -ne $expectedK2 -or $actualGame -ne $expectedGame) {
        throw "Installed reconnect hashes differ: k2=$actualK2 game=$actualGame"
    }
    [System.IO.File]::WriteAllText($log, ($output | Out-String))
} catch {
    [System.IO.File]::WriteAllText($log, ($_ | Out-String))
    exit 1
}
