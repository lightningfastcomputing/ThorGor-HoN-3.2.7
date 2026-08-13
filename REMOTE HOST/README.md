# Remote host DLL patchers

This folder is a self-contained copy of the ThorGor v61 DLL patch bundle. It
does not contain HoN DLLs or other game files. The installers accept only the
documented HoN 3.2.7.1 input hashes, preserve verified stock backups, build the
patches locally, and verify the resulting hashes before installation.

## Install

Close every HoN player, manager, and dedicated-server process. Open PowerShell
as Administrator in this folder, then run:

```powershell
./INSTALL_V61_PATCHES.ps1 -HonHome 'C:\Program Files (x86)\Heroes of Newerth'
```

Python 3.10 or newer is required on the machine generating the patches.

Expected installed hashes:

- `k2.dll`: `6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF`
- `game\cgame.dll`: `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`
