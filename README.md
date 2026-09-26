# ThorGor — HoN 3.2.7 LAN Sandbox (Refactored)

An isolated Heroes of Newerth 3.2.7.1 LAN backend with master/authentication,
chat, public games, dedicated-server management, matchmaking, and reproducible
binary patching.

## Reconnect v39 frozen milestone

This checkout contains the reconnect admission repair described in
[docs/RECONNECT.md](docs/RECONNECT.md). Run `INSTALL_RECONNECT_V39.bat` from
this checkout to install the verified patches and launch its dashboard.
Start a fresh match: earlier builds stored incorrect native account identities.
V39 preserves the complete live-proven v32 joiner reconnect path. Ghidra showed
that creator departure independently queues K2's `StopServer` command because
the creator occupies `CHostServer`'s special local-client field. V38 suppresses
only that command on a server-manager-owned dedicated slave. The v38 live trace
then showed player2 continuing to send while the slave sent zero state after
creator departure. V39 adds the isolated, previously safe-tested v35 successor
lookup so host migration can select that retained player despite its historical
map key. Normal local-host shutdown, admission, and reconnect identity remain
unchanged.
The rejected v26/v27 shared lookup and v30 roster-mutation experiments remain
absent. Read-only native player-map snapshots remain available
in `var/work/reconnect_identity_events.jsonl`. The 77-test suite passes with
two rejected-build checks intentionally skipped.

Live testing confirmed that both creator and joiner now reconnect correctly and
the slave survives either departure. One residual defect remains: creator
departure freezes the joiner's existing state stream until the joiner performs
their own disconnect/reconnect. This exact state is frozen locally as
`reconnect-v39-both-accounts-reconnect-milestone`.

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

These commands use the current reconnect work branch and the default HoN path.
Change `HON_HOME` when the game is installed elsewhere.

Acquire the current build:

```powershell
git clone --branch refactored-architecture-reconnect-wip --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"
```

Install or reinstall the verified reconnect v39 patches and start the stack:

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\INSTALL_RECONNECT_V39.bat"
```

Run an existing installation (patch verification is performed at startup):

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\START_STACK.bat"
```

Acquire, install, and run:

```powershell
git clone --branch refactored-architecture-reconnect-wip --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor"; if ($LASTEXITCODE -eq 0) { $env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\INSTALL_RECONNECT_V39.bat" }
```

Update an existing checkout, reinstall v39, and run:

```powershell
git -C "$env:USERPROFILE\thorgor" pull --ff-only origin refactored-architecture-reconnect-wip; if ($LASTEXITCODE -eq 0) { $env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\INSTALL_RECONNECT_V39.bat" }
```

Configure and launch one remote HoN client (replace the example IP):

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\START_REMOTE_CLIENT.bat" '192.168.1.10'
```

Configure once and launch three remote HoN clients:

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor\START_REMOTE_CLIENT_THREE_INSTANCES.bat" '192.168.1.10'
```

Open the account manager:

```powershell
& "$env:USERPROFILE\thorgor\START_ACCOUNT_MANAGER.bat"
```

`INSTALL_RECONNECT_V39.bat` elevates when needed, stops old ThorGor processes,
installs and verifies the supported binary patches, resets volatile state, and
starts the dashboard. `START_STACK.bat` performs the same patch verification
and state reset in the foreground during normal launches. Close all HoN clients
before installing or updating patched DLLs.

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
