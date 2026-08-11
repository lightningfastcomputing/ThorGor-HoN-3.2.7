$ErrorActionPreference = 'SilentlyContinue'

function Resolve-Python([string]$Command, [string[]]$PrefixArgs = @()) {
    if (-not $Command) { return $null }
    $resolved = & $Command @PrefixArgs -c 'import sys; assert sys.version_info >= (3, 10); print(sys.executable)' 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    $lines = @($resolved | Where-Object { $_ -and $_.Trim() })
    if (-not $lines.Count) { return $null }
    $path = $lines[-1].Trim()
    if ($path -and (Test-Path -LiteralPath $path -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $path).Path
    }
    return $null
}

$candidates = @()
if ($env:THORGOR_PYTHON_EXE) { $candidates += ,@($env:THORGOR_PYTHON_EXE, @()) }

$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notmatch '\\WindowsApps\\python(?:\.exe)?$') {
    $candidates += ,@($pythonCommand.Source, @())
}

$pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCommand) {
    $candidates += ,@($pyCommand.Source, @('-3.14'))
    $candidates += ,@($pyCommand.Source, @('-3'))
}

$localPrograms = Join-Path $env:LOCALAPPDATA 'Programs\Python'
foreach ($root in @($localPrograms, $env:ProgramFiles)) {
    if ($root -and (Test-Path -LiteralPath $root -PathType Container)) {
        Get-ChildItem -LiteralPath $root -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { $candidates += ,@((Join-Path $_.FullName 'python.exe'), @()) }
    }
}

foreach ($candidate in $candidates) {
    $path = Resolve-Python $candidate[0] $candidate[1]
    if ($path) {
        Write-Output $path
        exit 0
    }
}

throw 'Python 3.10+ was not found. Install it with: winget install --exact --id Python.Python.3.14'
