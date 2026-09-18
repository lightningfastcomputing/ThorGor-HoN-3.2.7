$ErrorActionPreference = 'Stop'

$repository = Split-Path -Parent $PSScriptRoot
$gameDirectory = if ($env:HON_HOME) { $env:HON_HOME } else { 'C:\Program Files (x86)\Heroes of Newerth' }
$python = (Get-Command python.exe -ErrorAction Stop).Source
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $process = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
        -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    exit $process.ExitCode
}

$env:HON_HOME = $gameDirectory
$env:THORGOR_HON_HOME = $gameDirectory
$env:PYTHONPATH = $repository
Set-Location -LiteralPath $repository
$logDirectory = Join-Path $repository 'work'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$log = Join-Path $logDirectory 'install_reconnect_v24.log'

try {
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($arguments in @(
        @('-m', 'thorgor', 'cleanup'),
        @('-m', 'thorgor', 'patches', 'install', '--hon-home', $gameDirectory),
        @('-m', 'thorgor', 'patches', 'verify', '--hon-home', $gameDirectory),
        @('-m', 'thorgor', 'reset-state')
    )) {
        $savedPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $result = & $python @arguments 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $savedPreference
        $text = ($result | ForEach-Object { $_.ToString() }) | Out-String
        $lines.Add("COMMAND: python $($arguments -join ' ')`n$text")
        if ($exitCode -ne 0) { throw "python exited $exitCode`n$text" }
    }
    $dashboard = Start-Process -FilePath $python `
        -ArgumentList '-m', 'thorgor', 'dashboard' `
        -WorkingDirectory $repository -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDirectory 'stack_v24.out.log') `
        -RedirectStandardError (Join-Path $logDirectory 'stack_v24.err.log')
    $lines.Add("Repository: $repository`nDashboard PID: $($dashboard.Id)")
    [System.IO.File]::WriteAllText($log, ($lines | Out-String))
} catch {
    [System.IO.File]::WriteAllText($log, ($_ | Out-String))
    Write-Error "Reconnect v24 installation failed. See $log"
    exit 1
}

