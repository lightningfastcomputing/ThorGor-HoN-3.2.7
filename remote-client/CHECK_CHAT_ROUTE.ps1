param([Parameter(Mandatory = $true)][string]$Server)
$hostName = 'chatserver.heroesofnewerth.com'
Write-Host 'ThorGor LAN chat route check' -ForegroundColor Cyan
try {
    $resolved = [Net.Dns]::GetHostAddresses($hostName) | Where-Object AddressFamily -eq InterNetwork
    Write-Host "$hostName resolves to: $($resolved.IPAddressToString -join ', ')"
} catch {
    Write-Host "$hostName did not resolve." -ForegroundColor Red
}
Test-NetConnection $Server -Port 11031 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
Write-Host ''
Write-Host "Expected: $hostName -> $Server and TcpTestSucceeded = True" -ForegroundColor Yellow
