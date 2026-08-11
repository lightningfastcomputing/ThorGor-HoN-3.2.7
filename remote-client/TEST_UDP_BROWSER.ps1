param([Parameter(Mandatory = $true)][string]$Server,[int]$Port=11236)
$udp = New-Object System.Net.Sockets.UdpClient
$udp.Client.ReceiveTimeout = 2500
try {
    $udp.Connect($Server,$Port)
    # HoN browser query: 00 00 01 CA + 2-byte token
    [byte[]]$q = 0x00,0x00,0x01,0xCA,0x34,0x12
    [void]$udp.Send($q,$q.Length)
    Write-Host "Sent HoN CA browser probe to ${Server}:$Port" -ForegroundColor Cyan
    $remote = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any,0)
    $reply = $udp.Receive([ref]$remote)
    $hex = ($reply | ForEach-Object { $_.ToString('X2') }) -join ' '
    Write-Host "UDP REPLY from $remote : $($reply.Length) bytes" -ForegroundColor Green
    Write-Host $hex
} catch {
    Write-Host "NO UDP REPLY from ${Server}:$Port within 2.5 seconds." -ForegroundColor Red
    Write-Host 'If the shim console also shows no BROWSER_RX, check Windows Firewall and that the shim says LISTEN 0.0.0.0:11236.' -ForegroundColor Yellow
} finally {
    $udp.Close()
}
