param([Parameter(Mandatory=$true)][string]$ServerIP)
$ErrorActionPreference='Stop'
$hosts = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$hostname = 'chatserver.heroesofnewerth.com'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 5 }
$parsed=$null
if (-not [Net.IPAddress]::TryParse($ServerIP,[ref]$parsed) -or $parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw "Invalid IPv4 address: $ServerIP" }
$lines=@(Get-Content -LiteralPath $hosts -ErrorAction Stop)
$escaped=[regex]::Escape($hostname)
$kept=@($lines | Where-Object { $_ -notmatch "^\s*(?:\d{1,3}\.){3}\d{1,3}\s+$escaped(?:\s|$)" })
$kept += "$ServerIP $hostname # ThorGor HoN LAN chat"
Set-Content -LiteralPath $hosts -Value $kept -Encoding ASCII
Clear-DnsClientCache -ErrorAction SilentlyContinue
exit 0
