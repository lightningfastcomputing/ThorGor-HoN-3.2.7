param([Parameter(Mandatory = $true)][string]$Server)
Write-Host "Testing ThorGor server $Server" -ForegroundColor Cyan
Test-NetConnection $Server -Port 80 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
Test-NetConnection $Server -Port 11031 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
Write-Host ''
Write-Host 'For UDP browser reachability run:' -ForegroundColor Yellow
Write-Host ".\TEST_UDP_BROWSER.ps1 $Server" -ForegroundColor Yellow
