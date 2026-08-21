# Remote host DLL patchers

This folder is a self-contained copy of the ThorGor v77/v61 DLL patch bundle. It
does not contain HoN DLLs or other game files. The installers accept only the
documented HoN 3.2.7.1 input hashes, preserve verified stock backups, build the
patches locally, and verify the resulting hashes before installation.

## Install

Close every HoN player, manager, and dedicated-server process. Open PowerShell
as Administrator in this folder, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL_V77_PATCHES.ps1 -HonHome 'C:\Program Files (x86)\Heroes of Newerth'
```

Python 3.10 or newer is required on the machine generating the patches.

Expected installed hashes:

- K2 v57 baseline: `6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF`
- Installed `k2.dll` v65: `82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB`
- Installed `k2.dll` v75: `9D731944738C6CA014CB71F25F82DCE8634522247AB935513E2F5A0889C0BFF3`
- Installed `k2.dll` v76: `FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0`
- Installed `k2.dll` v77: `25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026`
- `game\cgame.dll`: `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`
