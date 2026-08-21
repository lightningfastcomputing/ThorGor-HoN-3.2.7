$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'RESET_V42.ps1')

$work = Join-Path $PSScriptRoot 'work'
$runId = (Get-Content -LiteralPath (Join-Path $work 'v42_run_id.txt') -Raw).Trim()
Set-Content -LiteralPath (Join-Path $work 'v43_run_id.txt') -Value $runId -Encoding UTF8

Write-Host "v43 backend-bridge state reset. Run ID: $runId" -ForegroundColor Green
