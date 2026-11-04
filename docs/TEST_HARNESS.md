# Autonomous test harness

Run from the checkout root with Python 3.10 or later.

```powershell
py -m thorgor.tools.harness auth
py -m thorgor.tools.harness lobby-authority --report .\lobby-authority.json
py -m unittest discover -s tests
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

| Scenario | Passing evidence |
| --- | --- |
| `auth` | A wrong password fails SRP. Two correct logins verify the server proof and return distinct account IDs and cookies. Chat closes silently after the simulated client sends a crossed cookie and half-closes. Each correct identity receives the exact protocol-47 acceptance frame. |
| `lobby-authority` | All authentication checks pass. Master `c_conn` grants the first keyed request creator authority, admits the joiner with ordinary authority, and retains the creator reservation after the joiner tries to release it. The joiner can reserve after the creator releases it. |

## Native baseline and live verification

The canonical launch plan in `game_manager/stack.py` adds the UDP proxy,
manager bridge, original HoN manager, and native match-ID monitor. The retail
manager launches the dedicated slave through `hon.exe -manager`. The existing
client launcher can spawn multiple instances. Separate native profiles and
automated client input still need live verification. The current plan uses
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
