param(
    [string]$HonHome = ""
)

$ErrorActionPreference = "Stop"

$expected = [ordered]@{
    "game\resources0.s2z" = @{ Length = 1417008975L; Sha256 = "2BE52F0FBCF0CF93B614CD0A7A85BB7AC96FAB6D821069639255925719CE962B" }
    "game\textures.s2z"   = @{ Length = 528566683L;  Sha256 = "CED0382C06D8D7B8B6544CCFE04390E8E55B13D1027D53C57CBA46F33A32EB67" }
    "game\game_shared.dll" = @{ Length = 5705728L; Sha256 = "37BBC4706D06AE9857F2C56FDECE0E53F0E656A12ECDA6556CAE546CEC73506F" }
    "game\cgame.dll" = @{ Length = 2154496L; Sha256 = "88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988" }
}

function Find-HonHome {
    param([string]$Requested)

    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    $candidates += @(
        "C:\Program Files (x86)\Heroes of Newerth",
        (Get-Location).Path
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate "hon.exe") -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

$resolvedHome = Find-HonHome -Requested $HonHome
$reportPath = Join-Path $PSScriptRoot "REMOTE_ASSET_CHECK.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("ThorGor v61 remote asset parity check")
$lines.Add("Run time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")

if (-not $resolvedHome) {
    $lines.Add("RESULT: FAIL - hon.exe could not be found.")
    $lines.Add("Checked the supplied path, Program Files (x86), and the current folder.")
    $lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
    $lines | ForEach-Object { Write-Host $_ }
    exit 2
}

$lines.Add("HoN folder: $resolvedHome")
$lines.Add("")
$mismatchCount = 0

foreach ($relativePath in $expected.Keys) {
    $fullPath = Join-Path $resolvedHome $relativePath
    Write-Host "Checking $relativePath ..."
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        $lines.Add("MISSING | $relativePath")
        $mismatchCount++
        continue
    }

    $file = Get-Item -LiteralPath $fullPath
    $hash = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToUpperInvariant()
    $wanted = $expected[$relativePath]
    $sizeOk = ($file.Length -eq $wanted.Length)
    $hashOk = ($hash -eq $wanted.Sha256)
    $status = if ($sizeOk -and $hashOk) { "MATCH" } else { "MISMATCH" }
    if ($status -ne "MATCH") { $mismatchCount++ }

    $lines.Add("$status | $relativePath")
    $lines.Add("  size:   $($file.Length) (expected $($wanted.Length))")
    $lines.Add("  sha256: $hash")
    if (-not $hashOk) { $lines.Add("  expect: $($wanted.Sha256)") }
}

$lines.Add("")
if ($mismatchCount -eq 0) {
    $lines.Add("RESULT: PASS - remote game assets exactly match the known-good dev installation.")
} else {
    $lines.Add("RESULT: FAIL - $mismatchCount required file(s) are missing or different.")
    $lines.Add("Do not reinstall or overwrite anything yet; send this report back for the targeted repair.")
}

$lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
$lines | ForEach-Object {
    if ($_ -like "RESULT: PASS*") { Write-Host $_ -ForegroundColor Green }
    elseif ($_ -like "RESULT: FAIL*" -or $_ -like "MISMATCH*" -or $_ -like "MISSING*") { Write-Host $_ -ForegroundColor Red }
    else { Write-Host $_ }
}
Write-Host ""
Write-Host "Report saved to: $reportPath" -ForegroundColor Cyan

if ($mismatchCount -eq 0) { exit 0 }
exit 1
