# ThorGor — HoN 3.2.7 LAN Sandbox (Refactored)

An isolated Heroes of Newerth 3.2.7.1 LAN backend with master/authentication,
chat, public games, dedicated-server management, matchmaking, and reproducible
binary patching.

## Requirements

- Windows 10 or 11 with Windows PowerShell.
- [Git for Windows](https://git-scm.com/download/win) available as `git`.
- 64-bit [Python 3.10 or newer](https://www.python.org/downloads/windows/) available as `python`; use the normal Windows installer so Tkinter is included.
- Heroes of Newerth 3.2.7 installed at `C:\Program Files (x86)\Heroes of Newerth` (the clean-machine default).
- Administrator approval when the launcher installs/verifies the game patches and configures remote-client routing.

The core stack has no third-party Python package requirements.
Developers using another preserved game installation can set `HON_HOME` before
launching; for example, `$env:HON_HOME = 'C:\intelprop\Heroes of Newerth'`.

## PowerShell one-liners

Acquire and install:

```powershell
git clone --branch refactored-architecture-2026-08-24 --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"
```

Run an existing installation:

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\START_STACK.bat"
```

Acquire, install, and run:

```powershell
git clone --branch refactored-architecture-2026-08-24 --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"; if ($LASTEXITCODE -eq 0) { $env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\START_STACK.bat" }
```

`START_STACK.bat` verifies or installs the supported binary patches, clears
volatile ThorGor state, and starts the dashboard and backend services.

Use `START_REMOTE_CLIENT_THREE_INSTANCES.bat` to enter the stack IP once,
perform remote-client setup once, and launch three HoN clients together.

## Local stack performance

On machines with four or more logical CPUs, the stack automatically reserves
the highest-numbered logical CPU for the HoN dedicated slave instead of pinning
it to busy CPU 0. Clients launched through `START_REMOTE_CLIENT.bat` against the
same PC and the Python stack services automatically avoid that processor and
its adjacent SMT sibling, leaving the server's physical core uncontended.
This prevents local graphical clients and backend work from starving the server
simulation and producing repeated long frames.

Set `THORGOR_DEDICATED_CPU` before starting both the stack and local clients to
override the automatic choice. Use a logical CPU number such as `6`, or use
`off` to disable CPU isolation. Long per-route UDP tracing is disabled during
normal stack launches; the debug bundle and compact packet-rate logging remain
available.
