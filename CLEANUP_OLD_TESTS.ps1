$ErrorActionPreference='SilentlyContinue'
Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -match '^hon\.exe$' -and ($_.CommandLine -match ' -manager( |$)' -or $_.CommandLine -match ' -dedicated( |$)')) -or
  ($_.Name -match '^pythonw?(\.exe)?$' -and $_.CommandLine -match '(thorgor_hon_sandboxed_masterserver|thorgor_hon_chatserver|hon_udp_shim|hon_manager_tcp_proxy|hon_manager_status_bridge|hon_native_matchid_bridge|hon_join_probe|hon_v49_dashboard)')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Milliseconds 900
