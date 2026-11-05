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

## Unattended gameplay and creator-departure regression

```powershell
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --gameplay --artifacts .\work\gameplay-baseline --report .\work\gameplay-baseline.json
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --creator-disconnect --artifacts .\work\creator-regression --report .\work\creator-regression.json
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --creator-disconnect --native-variant v39 --expect-freeze --artifacts .\work\frozen-control
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --creator-disconnect --native-variant registry-continuity --artifacts .\work\repaired-continuity
```

Both flags imply two-client admission. `--gameplay` requires native phase 6,
two spawned hero entity indices, an advancing native clock, and independent
complete snapshot frames for both clients over a five-second baseline.
`--creator-disconnect` then sends creator C3 and observes the same joiner
socket and native client number for another 15 seconds. Only continuing
fresh snapshots pass. Frozen v39 deliberately returns exit code 1 with
`creator_departure_result.classification = reproduced_freeze`. An incomplete
baseline, partial-only snapshots, or decoder errors cannot establish this
regression. Inspect the classification and cleanup events as well as the exit
code; an arbitrary scenario failure is not proof of the freeze.

`--expect-freeze` is an explicit expected-bug control, permitted only with
v39 creator disconnection. It passes only when the frozen bug is reproduced;
its success does not mean continuity works. All ordinary runs require correct
behavior. `--native-variant registry-continuity` builds the separate successor
from verified v39 in the disposable installation. The original v39 builders,
installer default, and source installation remain unchanged. See the
[registry diagnosis](NATIVE_CLIENT_REGISTRY.md) for the repair and evidence.

The verified protocol sequence after admission is:

1. Reliable C5 loading completion for both clients; start C7 snapshot ACKs.
2. Reliable C8 01 with little-endian uint32 team (1/2) and slot 0.
3. C8 2F ready from both; C8 30 match-start request from the creator.
4. Wait for native hero selection/lock (phase 2/3), send C8 07 random hero
   from each client, and verify selected hero types in native player records.
5. Send ready again. At hero loading (phase 4), send C5 again and keep
   heartbeats, reliable ACKs, retransmissions, and C7 frame ACKs running.
6. Wait through native hero loading and prematch countdowns into phase 6.

C8 controls are recovered from the native cgame.dll callbacks. Each socket
owns its reliable sequence and pending ACK state. Server-random hero types
are recorded; the test does not depend on a particular hero. Normal native
hero loading and prematch timers take 30 and 90 seconds respectively. The
scenario waits for them and typically completes in about three minutes.
It does not modify native match phase or game speed to advance the match.

Read-only native phase, clock, team, selected type, and hero index inspection
requires game_shared.dll SHA-256
`37BBC4706D06AE9857F2C56FDECE0E53F0E656A12ECDA6556CAE546CEC73506F`.
This is authoritative live-server evidence; accepting a sent command cannot
satisfy the checks. Existing native match-ID synchronization is unchanged.

K2 commands 5A/5B carry plain/compressed snapshots; 5C fragments and 5D/5E
termination frames are reassembled with strict length, size, zlib, and frame
validation. Entity deltas remain opaque. Only a complete snapshot with a
newer decoded server frame increments fresh-state counters. C7 carries a
uint16 bit length of 32 followed by the last complete uint32 frame. This
supplies an empty client input snapshot without requiring rendered clients.
Per-client reports include packet types, snapshot candidates, complete and
fresh frame counts, decoder errors, reliable counts, and send/receive counts.

The regression gate requires the native slave to stay alive in phase 6 with
an advancing clock, the creator's native disconnected bit set, and the joiner's
disconnected bit clear with unchanged socket and native number. The last three
one-second windows classify sustained fresh frames as `continued_state`, or
zero fresh frames with continued client sends and absent/complete-stale
snapshots as `reproduced_freeze`. Other results are `inconclusive` and fail.
Active players clear their admission-transition bit 0x40 after C5, so that bit
is deliberately not required during the departure check. Passing continuity
requires fresh frames in every one of the 15 windows, with advancing native
time and unchanged match ID, retained player pointer, client number, team,
hero index/type, native connection pointer, and upstream endpoint. A brief
early stall followed by healthy final windows still fails this gate.

Hash-gated read-only transport inspection records the registry root and linked
clients, native receive time and acknowledged frame, and the newly generated
CSnapshot frame/time from the native snapshot pool. The report retains the
last 80 per-route proxy counter windows and route endpoints without raw packets.
This distinguishes generation, recipient enumeration, native transmission,
and downstream delivery. Player state alone cannot establish any of them.

Team chat, movement/ability input, graphical rendering, and reconnect recovery
controls remain separate from the creator-departure scenario. No graphical instances or manual
input are needed for the active-match baseline or creator-departure test.

## Independent departure and snapshot recovery

```powershell
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant registry-continuity --joiner-disconnect --artifacts .\work\joiner-departure
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant registry-continuity --reconnect-cycle both --artifacts .\work\both-recovery
```

`--reconnect-cycle` accepts creator, joiner, or both. The combined scenario
disconnects/rejoins the joiner first, then the creator in the same active match.
Each departure requires 15 seconds of uninterrupted survivor snapshots. The
returning account uses a fresh authenticated socket while the other client is
continuously pumped. It must retain the same native CPlayer pointer, team,
selected/spawned hero, and match ID. A new native client number is allowed and
must match the active transport record. Inactive historical connections are
recorded, with active records selected by both account and live native number.

Initial world/state transfer can take more than five seconds. The harness
allows at most 30 seconds for eight fresh complete frames beyond the departure
frame, then requires both streams over a separate five-second baseline. Native
admission or a cleared disconnect bit alone cannot pass recovery. Live testing
verified both accounts' retained identity and snapshot resynchronization;
movement, ability control, rendering, and selection-phase recovery require
their own assertions.

## Selection recovery, termination, and repeated matches

```powershell
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant registry-continuity --hero-selection-reconnect both --artifacts .\work\selection-recovery
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant selection-recovery --hero-selection-reconnect both --pick-after-reconnect --creator-disconnect --artifacts .\work\unpicked-recovery
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant registry-continuity --terminate-match --artifacts .\work\native-ending
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --native-variant registry-continuity --repeat-matches 2 --artifacts .\work\consecutive-matches
```

Selection recovery disconnects/rejoins the requested roles after hero choice
and before readying. Their native team and selected hero must survive, and the
match must subsequently reach active gameplay with both snapshot streams.
Both roles passed this test.

`--pick-after-reconnect` moves the departures before hero choice and tests
the creator first when both roles are selected. The joiner must receive fresh
snapshots on the same socket for 15 seconds during the selection countdown
before the creator returns. Both returning players must retain their player
record, match and team, receive fresh snapshots under their assigned native
client number, and successfully choose a hero. The `selection-recovery`
variant combines the K2 registry fix with the direct and random hero-pick
lookup repair. The same selection scenario on v39 fails with
`reproduced_freeze` in phase 3.
The optional creator-departure check runs after both heroes spawn and the
match reaches active gameplay.

Termination uses the creator's native-admin C6 remote-console path to execute
`EndMatch 1`. It requires native phase 7, then lifecycle completion; the
verified build clears its game context after a 21-second ending countdown.
The lifecycle scenarios register a backend server session before admission if
the hybrid manager flow has no server/manager session. A separate hash-verified
native observer must see phase 7 and the same context subsequently cleared
before it sends an authenticated completion notification. Synthetic bridge
Idle status cannot satisfy it.

Repeated matches keep the same backend services and manager/slave job. Every
round must end natively and release backend ownership. The next match must
receive a different ID, begin with an empty hero selection in phase 1, admit
two native identities, and deliver state to both in phase 6. Two consecutive
matches passed on the same slave. See [lifecycle evidence](NATIVE_MATCH_LIFECYCLE.md).

## Current movement blocker

`--movement` is an experimental failing gate. It independently verifies hero
index, type, native owner, and server coordinates. The current simulated clients
have empty native control-selection sets and the test reports
`native_control_selection_missing`, then exits 1. It does not send ineffective
orders and claim success. Establishing control selection requires the newer
C7 input-entity snapshot encoding, which differs from the available older
source. C8 40 is unsupported by this binary; the verified C8 1E positional-order
payload uses a 16-bit single-entity index. Movement, abilities, rendering, and
decoded per-entity client position updates remain unproven.

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

The v39 freeze has now been reproduced unattended against a dedicated slave
with two independent simulated protocol clients. The frozen DLL hashes in
[the v39 notes](../Reconnect-v39-notes.md) remain unchanged. The native server
stays active while the already-connected joiner stops receiving snapshots
after creator departure. See [autonomous progress](AUTONOMOUS_PROGRESS.md)
for the latest run evidence and resume instructions. The separate managed
registry successor preserves the surviving connection chain during head
destruction. Reconnect identity and hero/control behavior are independently
tested concerns; a snapshot-continuity pass alone does not prove them.
