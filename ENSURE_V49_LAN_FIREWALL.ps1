param()
$ErrorActionPreference='Stop'

# This helper is deliberately limited to the three ThorGor LAN listener ports.
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'))
    $proc = Start-Process powershell.exe -Verb RunAs -ArgumentList $args -Wait -PassThru
    exit $proc.ExitCode
}

$rules = @(
    @{Name='ThorGor HoN v49 LAN Master TCP 80'; Protocol='TCP'; LocalPort='80'},
    @{Name='ThorGor HoN v49 LAN Chat TCP 11031'; Protocol='TCP'; LocalPort='11031'},
    @{Name='ThorGor HoN v49 LAN Public UDP 11236'; Protocol='UDP'; LocalPort='11236'}
)
foreach($r in $rules){
    $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    if($existing){
        Set-NetFirewallRule -DisplayName $r.Name -Enabled True -Direction Inbound -Action Allow -Profile Any | Out-Null
        # Make sure protocol/port didn't drift from an old experimental rule.
        Set-NetFirewallRule -DisplayName $r.Name -Direction Inbound -Action Allow -Enabled True -Profile Any | Out-Null
        $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol $r.Protocol -LocalPort $r.LocalPort | Out-Null
    } else {
        New-NetFirewallRule -DisplayName $r.Name -Direction Inbound -Action Allow -Profile Any -Protocol $r.Protocol -LocalPort $r.LocalPort | Out-Null
    }
}
exit 0
