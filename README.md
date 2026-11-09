# ThorGor — HoN 3.2.7 LAN Sandbox (Refactored)

An isolated Heroes of Newerth 3.2.7.1 LAN backend with master/authentication,
chat, public games, dedicated-server management, matchmaking, and reproducible
binary patching.

The [test harness](docs/TEST_HARNESS.md) runs unattended master, chat, and
backend lobby-authority scenarios with disposable accounts on loopback.
It also starts a real native manager/slave, admits two protocol clients,
selects heroes, and verifies active gameplay and independent snapshot streams.
Its creator-departure regression reproduces the frozen v39 joiner stream.
The separate `registry-continuity` native variant repairs that freeze and has
passed three fresh 15-second continuity tests. The harness also verifies
retained-hero snapshot recovery, hero-selection reconnect, native termination,
and consecutive matches. The normal installer defaults to frozen v39.
The `selection-recovery` build combines the registry repair with the hero
selection and repeat departure repairs. Graphical testing confirmed that
the joiner stays connected after the host leaves and both players can pick a
hero after reconnecting. Use `START_SELECTION_RECOVERY.bat` with the
separate game copy described in the [manual test guide](docs/MANUAL_TEST.md).

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
- Heroes of Newerth 3.2.7.1 installed at `C:\Program Files (x86)\Heroes of Newerth` (the clean-machine default).
- Administrator approval when the launcher installs/verifies the game patches and configures remote-client routing.

The core stack has no third-party Python package requirements.
Developers using another preserved game installation can set `HON_HOME` before
launching; for example, `$env:HON_HOME = 'C:\intelprop\Heroes of Newerth'`.

## PowerShell one-liners

These commands use the refactored-testing-harness-reconnect-fixed branch in
`%USERPROFILE%\thorgor-reconnect-fixed`. If you already have this branch
checked out elsewhere, use that folder in the launcher commands. Close all HoN
clients before installing or updating patched DLLs.

### Frozen v39 comparison

Acquire, install, and run from a fresh checkout:

```powershell
git clone --branch refactored-testing-harness-reconnect-fixed --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor-reconnect-fixed"; if ($LASTEXITCODE -eq 0) { $env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor-reconnect-fixed\INSTALL_RECONNECT_V39.bat" }
```

The destination must be absent or empty. Change `HON_HOME` in the command
if HoN is installed elsewhere. The installer requests administrator approval,
installs and verifies the patches, and starts the dashboard.

Run an existing checkout from an Administrator PowerShell:

```powershell
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'; & "$env:USERPROFILE\thorgor-reconnect-fixed\START_STACK.bat"
```

Start the account manager:

```powershell
& "$env:USERPROFILE\thorgor-reconnect-fixed\START_ACCOUNT_MANAGER.bat"
```

### Selection-recovery build

For a fresh checkout, acquire this branch:

```powershell
git clone --branch refactored-testing-harness-reconnect-fixed --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git "$env:USERPROFILE\thorgor-reconnect-fixed"
```

Place a complete HoN 3.2.7.1 installation in
`%USERPROFILE%\thorgor-reconnect-fixed\work\manual-test\Heroes of Newerth`.
This launcher patches that separate game copy.

Start the repaired stack from an Administrator PowerShell:

```powershell
& "$env:USERPROFILE\thorgor-reconnect-fixed\START_SELECTION_RECOVERY.bat"
```

Wait for **Native build: selection-recovery** and **Public Server Ready** in
the dashboard. Start two local test clients from a second Administrator
PowerShell:

```powershell
& "$env:USERPROFILE\thorgor-reconnect-fixed\START_SELECTION_RECOVERY.bat" clients
```

See the [manual test guide](docs/MANUAL_TEST.md) for LAN addresses, test
accounts, and the reconnect checks.

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
