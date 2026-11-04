# Autonomous test harness

Run from the checkout root with Python 3.10 or later.

```powershell
py -m thorgor.tools.harness auth
py -m thorgor.tools.harness lobby-authority --report .\lobby-authority.json
py -m unittest discover -s tests
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --artifacts .\work\native-evidence
```

The CLI writes timestamped JSON to standard output. Exit code 0 means the
checks and cleanup passed. Exit code 1 means the scenario or cleanup failed.
`--report` creates a new file. The harness provisions two accounts with random
passwords, gives master and chat OS-assigned loopback ports, and removes its
runtime directory after reaping both processes. Passwords are passed to the
provisioning command through its environment. The existing services write raw
diagnostics to the disposable directory. Shared reports retain step names,
results, error classes, and process IDs.

If the Windows runner restricts its default temporary directory, point
`TMP` and `TEMP` at a writable test directory before invoking Python. The
backend scenarios also require permission to connect to local loopback sockets.

`--artifacts` creates a new directory and appends credential-free JSON events
during execution. Use a fresh path for each run. The final JSON still goes to
standard output and optionally `--report`.

| Scenario | Passing evidence |
| --- | --- |
| `auth` | A wrong password fails SRP. Two correct logins verify the server proof and return distinct account IDs and cookies. Chat closes silently after the simulated client sends a crossed cookie and half-closes. Each correct identity receives the exact protocol-47 acceptance frame. |
| `lobby-authority` | All authentication checks pass. Master `c_conn` grants the first keyed request creator authority, admits the joiner with ordinary authority, and retains the creator reservation after the joiner tries to release it. The joiner can reserve after the creator releases it. |
| `native-match` | The copied DLLs match v39. Real master, chat, UDP proxy, manager bridge, native manager, and dedicated slave start. An owned slave sends its real `0x40` association and receives a real manager wake or reports its own readiness. It owns UDP 11235 and loads the staged verified game DLL. Authenticated simulated accounts work while it remains alive. The Windows job, Python services, test profile, and temporary installation are cleaned up. |

## Real native execution

The source installation is copied into a disposable directory. Patches are
applied only to that copy and the loaded game DLL is checked against v39.
The staged directory contains spaces because the legacy manager-generated slave
command line discarded the dedicated arguments when tested from a path without
spaces. Native process ownership is established before resuming the manager,
using a Windows job with kill-on-close. Descendants are tracked and waited for
during cleanup. Reported exit code 1 is the deliberate forced cleanup code.

This scenario currently requires the canonical ports 80, 11031, 1135, 1136,
11235, and 11236 to be free, plus existing HoN instances to be closed. Python
listeners use loopback. The tested native slave binds `0.0.0.0:11235` despite
its loopback advertised address. Native bindings are recorded in the report.
The test creates a uniquely named mod/profile and preserves and restores the
shared bootstrap console log. HoN still accesses its standard profile during
early bootstrap, so separate graphical-client profiles remain incomplete.
The harness leaves Windows hostname routing and firewall configuration alone.

The report includes native DLL hashes, loaded-module verification, owned PIDs,
exit codes, real control-frame counts and a filtered frame log, sampled UDP
route counts, and a filtered shared-state snapshot. The snapshot explicitly
identifies bridge-synthetic status. The native association and manager wake
provide the readiness evidence. Raw credentials and packets remain in the
temporary runtime and are removed with it.

## Two simulated clients

```powershell
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --admit-clients --artifacts .\work\admission-evidence
```

This extension uses separate authenticated identities and UDP
sockets. Its C0 trailer, C9 keepalive, reliable ACKs, and C2/C4 ready messages
are based on preserved local native-client traces. It obtains a creator key
through the actual server-list API, bootstraps the creator, reserves a lobby
through the authenticated backend, and uses the existing bridge's `0x26`
start path. Native match-ID synchronization uses the existing implementation
against the owned, hash-verified slave only. It then attempts joiner bootstrap
and requires two distinct account IDs and native client numbers with connected
status in the authoritative player map. Timeout or missing native state fails
the extension. A successful transport bootstrap alone does not pass it.

## Console and match control

| Mechanism | Verified repository behavior |
| --- | --- |
| Startup `-execute` | Configures the retail manager and slave settings. |
| Manager `0x21` | Wakes the associated slave. Observed during native smoke tests. |
| Manager `0x25` | Existing console-command encoder sends `Set svr_maxClients 10`. Optional diagnostic code also sends `Set svr_sendStatusToManager 1`. Injection alone establishes transmission. |
| Manager `0x26` | Existing bridge sends the reserved match name, options, and two integer arguments to the slave. Native game context and roster checks establish the resulting state separately. |
| Authenticated `host_lobby` | Allocates the backend lobby and triggers the bridge watcher. |
| `ManagerInstanceRcon` | Found as a native console command string. An external RCON transport has not been verified. |

The verified run admitted accounts 1 and 2 with native client numbers 0 and 1.
It observed both native connected bits and completed cleanup. No `0x46`
start-result acknowledgment appeared. The acceptance checks use the owned
slave's game context and player map.

Hero selection, team chat, active gameplay initiation, state-stream continuity, and
disconnect/reconnect still require further protocol or isolated native-client
automation. Graphical gameplay coverage remains unverified.

## Native baseline and live verification

The canonical launch plan in `game_manager/stack.py` adds the UDP proxy,
manager bridge, original HoN manager, and native match-ID monitor. The retail
manager launches the dedicated slave through `hon.exe -manager`. The existing
client launcher can spawn multiple instances. Separate graphical-client profiles
and automated client input still need live verification. The current plan uses
fixed ports and client setup can edit Windows hostname routing.

On the audited Windows host, Python 3.14 was available. The installed
`C:\intelprop\Heroes of Newerth` contained `hon.exe` and stock `k2.dll` and
`game\game.dll` matching the patch inputs. For instruction emulation, copy
those verified DLLs to a disposable fixture as
`k2.dll.thorgor_stock_3.2.7.1` and
`game\game.dll.thorgor_stock_3.2.7.1`. Set `THORGOR_TEST_HON_HOME` to that
fixture and run the suite with `pefile` and `unicorn` importable. The tests
rebuild the native patches in a temporary directory and exercise the manager
stop suppression and host-successor selection.

The v39 live freeze remains to be reproduced with a dedicated slave and two
isolated real clients. Start with a fresh match and pin both DLL hashes to
[the frozen v39 notes](../Reconnect-v39-notes.md). Establish that both players
receive gameplay state before disconnecting the creator. Correlate creator C3,
the slave PID and lifecycle, the joiner's unchanged UDP route, per-route
`ROUTE_STATS`, and decoded state messages before and after departure. Treat a
silent joiner route as evidence of the freeze only while the slave stays alive
and the joiner keeps sending. Reconnect the joiner as a recovery control. Report
missing baseline state, missing PID or route evidence, or an interrupted test
as inconclusive. Use the native identity snapshots to investigate whether host
selection, live identity, or state-recipient delivery first diverged.
