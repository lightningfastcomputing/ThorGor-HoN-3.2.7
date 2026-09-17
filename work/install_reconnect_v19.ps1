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
$python = 'C:\Python314\python.exe'
$expectedK2 = 'FF053A133261FD565B6656AE24F5182AA2423195EA9B77C304128045BBD33A6B'
$expectedGame = '929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B'
$env:HON_HOME = $gameDirectory
$env:THORGOR_HON_HOME = $gameDirectory
$env:PYTHONPATH = $repository
$log = Join-Path $repository 'work\install_reconnect_v19.log'
$stdout = Join-Path $repository 'work\stack_v19.out.log'
$stderr = Join-Path $repository 'work\stack_v19.err.log'
Set-Location $repository

try {
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($arguments in @(
        @('-m', 'thorgor', 'cleanup'),
        @('-m', 'thorgor', 'patches', 'install', '--hon-home', $gameDirectory),
        @('-m', 'thorgor', 'reset-state')
    )) {
        $result = & $python @arguments 2>&1
        $lines.Add(($result | Out-String))
        if ($LASTEXITCODE -ne 0) {
            throw ($result | Out-String)
        }
    }

    $actualK2 = (Get-FileHash -LiteralPath (Join-Path $gameDirectory 'k2.dll') -Algorithm SHA256).Hash
    $actualGame = (Get-FileHash -LiteralPath (Join-Path $gameDirectory 'game\game.dll') -Algorithm SHA256).Hash
    if ($actualK2 -ne $expectedK2 -or $actualGame -ne $expectedGame) {
        throw "Installed reconnect hashes differ: k2=$actualK2 game=$actualGame"
    }

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    $dashboard = Start-Process -FilePath $python `
        -ArgumentList '-m', 'thorgor', 'dashboard' `
        -WorkingDirectory $repository `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    $lines.Add("Dashboard PID: $($dashboard.Id)")
    [System.IO.File]::WriteAllText($log, ($lines | Out-String))
} catch {
    [System.IO.File]::WriteAllText($log, ($_ | Out-String))
    exit 1
}
