# ThorGor — HoN 3.2.7 LAN Sandbox (Refactored)

An isolated Heroes of Newerth 3.2.7.1 LAN backend with master/authentication,
chat, public games, dedicated-server management, matchmaking, and reproducible
binary patching.

## Requirements

- Windows 10 or 11 with Windows PowerShell.
- [Git for Windows](https://git-scm.com/download/win) available as `git`.
- 64-bit [Python 3.10 or newer](https://www.python.org/downloads/windows/) available as `python`; use the normal Windows installer so Tkinter is included.
- Heroes of Newerth 3.2.7 installed at `C:\intelprop\Heroes of Newerth`, or set `HON_HOME` to its installation directory before launching.
- Administrator approval when the launcher installs/verifies the game patches and configures remote-client routing.

The core stack has no third-party Python package requirements.

## PowerShell one-liners

Acquire and install:

```powershell
git clone --branch refactored-architecture-2026-08-24 --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"
```

Run an existing installation:

```powershell
& "$env:USERPROFILE\thorgor\START_STACK.bat"
```

Acquire, install, and run:

```powershell
git clone --branch refactored-architecture-2026-08-24 --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"; if ($LASTEXITCODE -eq 0) { & "$env:USERPROFILE\thorgor\START_STACK.bat" }
```

`START_STACK.bat` verifies or installs the supported binary patches, clears
volatile ThorGor state, and starts the dashboard and backend services.
