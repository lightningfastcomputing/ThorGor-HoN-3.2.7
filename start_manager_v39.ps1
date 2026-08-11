$ErrorActionPreference='Stop'
$honHome='C:\intelprop\Heroes of Newerth'
$hon=Join-Path $honHome 'hon.exe'
if(!(Test-Path $hon)){throw "hon.exe not found: $hon"}
$settings=@(
 'Set man_masterLogin thorgorhost:',
 'Set man_masterPassword test123',
 'Set man_port 1136',
 'Set man_numSlaveAccounts 1',
 'Set man_idleTarget 1',
 'Set man_startServerPort 11235',
 'Set man_endServerPort 11235',
 'Set man_maxServers 1',
 'Set man_broadcastSlaves true',
 'Set man_autoServersPerCPU 1',
 'Set man_allowCPUs 0',
 'Set man_reauthFrequency 30000',
 'Set svr_name ThorGor Public 0 0',
 'Set svr_location USE',
 'Set svr_ip 127.0.0.1',
 'Set svr_port 11234',
 'Set svr_broadcast true',
 'Set svr_chatAddress 127.0.0.1',
 'Set svr_chatPort 11031',
 'Set svr_maxClients 10',
 'Set host_affinity -1',
 'Set upd_checkForUpdates false'
)-join ';'
Write-Host 'v39: original manager TCP 1136; readiness/status bridge TCP 1135; real slave UDP 11235; public picker shim UDP 11236.' -ForegroundColor Green
& $hon -manager -noconfig -execute $settings -masterserver 127.0.0.1
