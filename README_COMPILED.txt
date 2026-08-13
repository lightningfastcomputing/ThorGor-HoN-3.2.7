ThorGor HoN v61 compiled distribution
======================================

Start the complete LAN stack with:

  1_START_V61_COMPLETE_REGISTRY_GUARD.bat

The compiled distribution does not require Python on the computer running it.
It still requires Administrator approval because the launcher configures the
Windows Firewall and installs the verified v57/v61 DLL patches into the local
HoN 3.2.7.1 installation at C:\Program Files (x86)\Heroes of Newerth.

Executables:
  ThorGorDashboard.exe       GUI and service orchestrator
  ThorGorMasterServer.exe    authentication and server-list service
  ThorGorChatServer.exe      LAN chat service
  ThorGorUdpShim.exe         public-list UDP bridge
  ThorGorManagerBridge.exe   manager/slave control bridge
  ThorGorNativeBridge.exe    native match-ID bridge
  ThorGorAccountManager.exe  optional account-management console

To rebuild, run BUILD_COMPILED.ps1 from PowerShell. PyInstaller is needed only
on the build computer, not on computers running this compiled distribution.
