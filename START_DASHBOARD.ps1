param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,

    [string]$LanIp = ""
)

$ErrorActionPreference = 'Stop'

$dashboard = Join-Path $PSScriptRoot 'hon_v49_dashboard.py'
$logDirectory = Join-Path $PSScriptRoot 'dashboard_logs'
$stdoutLog = Join-Path $logDirectory 'dashboard-startup.stdout.log'
$stderrLog = Join-Path $logDirectory 'dashboard-startup.stderr.log'

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Validated Python executable is missing: $PythonExe"
}
if (-not (Test-Path -LiteralPath $dashboard -PathType Leaf)) {
    throw "Dashboard script is missing: $dashboard"
}

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Remove-Item -LiteralPath $stdoutLog, $stderrLog -Force -ErrorAction SilentlyContinue

$arguments = @("`"$dashboard`"")
if ($LanIp) {
    $arguments += $LanIp
}

$process = Start-Process -FilePath $PythonExe `
    -ArgumentList $arguments `
    -WorkingDirectory $PSScriptRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

# Tk initialisation and the first event-loop turn happen immediately. A short
# wait catches missing-Tk and import failures that cmd.exe's `start` hid.
Start-Sleep -Seconds 2
if ($process.HasExited) {
    $details = @()
    if (Test-Path -LiteralPath $stderrLog) {
        $details += Get-Content -LiteralPath $stderrLog -Tail 40 -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $stdoutLog) {
        $details += Get-Content -LiteralPath $stdoutLog -Tail 40 -ErrorAction SilentlyContinue
    }
    $suffix = if ($details.Count) {
        [Environment]::NewLine + ($details -join [Environment]::NewLine)
    } else {
        " Check $stderrLog."
    }
    throw "Dashboard exited during startup with code $($process.ExitCode).$suffix"
}

Write-Host "Dashboard started (PID $($process.Id))." -ForegroundColor Green
Write-Host "Startup diagnostics: $stderrLog" -ForegroundColor DarkGray
