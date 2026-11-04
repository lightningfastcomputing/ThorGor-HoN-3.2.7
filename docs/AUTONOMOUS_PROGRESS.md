# Autonomous development progress

## Phase 4: verified active-match snapshot recovery

Repair milestone b43aa8b is committed locally. The combined --reconnect-cycle
both scenario on registry-continuity passed in a fresh native match. Joiner
departure preserved 15 seconds of creator snapshots; the joiner returned as
native client 2 with the same CPlayer/team/hero. Creator departure then
preserved 15 seconds of reconnected joiner snapshots; the creator returned as
client 3 with its own retained CPlayer/team/hero. Both streams resynchronized
and advanced beyond departure frames (joiner 2861 -> 3380; creator 3380 -> 3899).
Evidence: ../../outputs/creator-freeze-session/recovery-both-2.json.
The complete recovery suite ran 109 tests: 107 passed, two historical skips
(recovery-suite.txt). Both departed/reconnected accounts were tested without
human input, and cleanup completed.

The first recovery probe correctly failed its five-second stream check before
the initial bulk state transfer finished. A bounded 30-second wait for eight
fresh frames now precedes the independent stream baseline. It does not waive
the passing baseline. Cleanup telemetry now retains endpoints before sockets
close, preventing a closed-socket exception from masking scenario results.

Verified scope is native retained identity and snapshot resynchronization,
including creator rejoining an existing match. No rendering or movement/control
claim is made. Next: authoritative movement, selection-phase reconnect,
termination/lifecycle, and repeated-match state clearing. Movement investigation
identified game+20 -> entity directory, its +10 vector indexed by hero ID,
entity index +10/type +38/owner +444, and position +98/+9C/+A0. These offsets
come from audited binary instructions and still need the live movement test.
The newer C7 input uses entity snapshots rather than the older source's fixed
input struct; old GAME_CMD_SELECTION 40 is unsupported in this binary.

## Creator-freeze repair continuation from 371db03

On 2026-11-04, fresh auth, lobby-authority, original native admission, and
active gameplay all passed. Two additional disposable v39 creator-departure
runs both failed with reproduced_freeze and completed cleanup. Machine-readable
reports are under ../../outputs/creator-freeze-session/ (auth.json, lobby.json,
admission.json, gameplay.json, v39-freeze-1.json, v39-freeze-2.json).

Read-only live observation in registry-observer.jsonl isolated a native
registry-root loss. Before C3, CHostServer+180 points to creator client 0,
whose +8430 points to joiner client 1. After C3, the head is null while the
joiner object remains in-game (state 4), same account and native number. Its
last receive time and acknowledged frame stop advancing. Server frame/time
and the native snapshot ring continue advancing. The v39 linked GetClient,
input dispatch, state queue, and send loops all start at that same head.

The retail cleanup at K2 RVA 2F2E4A frees the head and clears +180. The v38
StopServer suppression keeps the slave alive but does not preserve the linked
registry. This is supported by disassembly of the actual v39 DLL and the
local older HoN source's K2_CLIENT RemoveClient implementation; the binary
remains authoritative. No proxy route rewrite is needed to explain the loss.

A separate managed_registry builder now produces candidate K2 SHA-256
98138B1086092558014B4808D3AA75B00BA87450EA3112171F68CC3DC99048C2 from frozen
v39. It saves/detaches the successor before destroying a managed head and
preserves the successor as the registry root. Unmanaged cleanup remains stock.
Five instruction-emulation tests pass, including freed-memory poisoning,
multiple survivors, last/empty head, unmanaged behavior, and execution of the
real snapshot-recipient dispatch loop after removal.

The harness now separates --expect-freeze on explicit v39 from the desired
continuity gate, which requires fresh snapshots in every one of 15 windows.
Read-only transport evidence includes native endpoints, client registry,
ACK/receive counters, and generated snapshot metadata. Per-route proxy windows
are retained without credentials. Instrumented v39 reproduced the freeze for
all 15 windows. Generated native snapshots advanced 2879 -> 3161 while its
registry root was null and the proxy forwarded 20 joiner packets/second but
received zero back. This proves generation continues and transmission stops
because recipient enumeration loses the registry root.

All three repaired fresh matches passed all 15 continuity windows, with
20-21 fresh frames/second, stable native match/player/hero/connection/endpoint
identities, advancing native acknowledgments, and cleanup. Reports are
registry-repair-1.json, registry-repair-2.json, and registry-repair-3.json.
The pre-repair expanded suite ran 105 tests, with 103 passing and two historical
skips. The final repair suite ran 107 tests: 105 passed, two historical cases
skipped. See repair-suite.txt. No candidate was promoted based on command
acceptance alone. The registry repair is independently verified and ready for
its local milestone commit.
Next: expand independent departure/reconnect and movement scenarios. All work remains
local; the normal installer still selects frozen v39.

## Starting point

Work continues from local commit a917b55 on dev/autonomous-harness.
Native manager/slave startup and two simulated clients with distinct connected
native roster identities are verified. Auth and lobby-authority scenarios pass.
The v39 K2 and game DLL hashes remain pinned in the harness.

## Current milestone

Automate hero selection and active gameplay, establish state delivery to both
clients, then disconnect the creator and reproduce the remaining v39 freeze.
Reconnect fixes require a reproducible failing regression first.

Completed: native-match now supports --gameplay and --creator-disconnect.
The positive active-gameplay baseline passes; the frozen v39 departure
regression fails reproducibly with authoritative evidence.

## Verified discovery

- Preserved native-client scripts use Team(1, 0), Team(2, 0),
  SetPotentialHero('Hero_Chipper', ''), RandomHero(), Ready(), and
  RequestMatchStart() through client UI console functions.
- The native server contains StartMatch and OrderBot console commands.
- The manager bridge already encodes opcode 0x25 console commands and opcode
  0x26 lobby creation.
- game_shared.dll exports phase predicates, CPlayer::SelectHero,
  CPlayer::SetTeam, and CPlayer::SetHeroIndex. Their implementations can provide
  read-only native state offsets and evidence for phase transitions.

## Verified native gameplay probe

The first unattended probe selected teams 1 and 2, requested match start,
selected two heroes, and reached native phases 2, 3, 4, then 5. Both native
hero entity indices became valid in phase 5. The probe timed out during the
normal prematch timer before phase 6.

Recovered client game commands use reliable C8 envelopes.

| Command | Payload |
| --- | --- |
| 01 | Little-endian uint32 team and uint32 slot |
| 07 | Random hero selection, no additional payload |
| 2F | Ready, no additional payload |
| 30 | Creator match-start request, no additional payload |
| BD | Potential hero, uint16 native entity type plus NUL avatar string |

The command values come from the audited cgame.dll callbacks. Reliable
sequence numbers are tracked independently for each simulated client.

Read-only native offsets verified against game_shared.dll exports include
CGameInfo phase at +78, phase duration at +80, CPlayer team at +70,
hero entity index at +74, and selected hero type at +84.

## Reproduced v39 freeze

Probe 2 reached native active phase 6 with two spawned heroes. Both clients
received approximately 20 complete snapshot frames per second over a
five-second baseline. After creator C3, the joiner received zero packets for
five consecutive seconds while sending approximately 20 packets per second.
Its last snapshot frame stayed at 2858. Native engine time advanced from
142950 to 148050, phase stayed at 6, the slave survived, and the joiner's
native client number stayed at 1. The emitted regression classification was
reproduced_freeze. The scenario correctly returned a failure exit code.

Evidence is in work/gameplay-probe-2.json and work/gameplay-probe-2/events.jsonl.
All native and Python processes, the copied installation, and the test
profile were cleaned up.

The active client uses reliable C5 loading completion and C7 frame
acknowledgments. Normal prematch duration was observed as 90000 ms and hero
loading as 30000 ms. The active-phase deadline includes a margin over both.

K2 snapshot handlers at RVAs 30A910, 309970 and 30A670 identify complete
snapshots 5A/5B, fragments 5C, and final fragments 5D/5E.
The first decoded snapshot uint32 is the server frame number. C7 contains
a uint16 bit length followed by the client snapshot bit buffer. The empty
input buffer has 32 bits containing the last complete server frame.

The creator-departure check is gated on phase 6, valid native heroes,
advancing native time, and fresh complete snapshots for both clients.
It keeps the joiner endpoint and native client number unchanged. Snapshot
decode errors and incomplete fragments produce an inconclusive result.

Active native player records clear their initial connection-transition bit
0x40 after C5. The departure check uses the documented disconnected bit 0,
stable native client number, stable UDP endpoint, and continuing client sends.
It does not require transition bit 0x40 to remain set during gameplay.

## Fresh verification on 2026-11-04

The final creator-departure run reproduced the freeze at 09:47 Eastern.
Both independent clients received 20-21 complete fresh frames per second.
After C3, the joiner received zero packets and frames in all five windows,
while sending 20,20,20,20,19 packets. Its last frame remained 2858. Native
engine time advanced from 142950 to 148050 in active phase 6. Joiner client
number 1 and UDP endpoint 127.0.0.1:65527 stayed unchanged. The creator's
native disconnected bit was set; the joiner's was clear. Decoder errors were
zero. The regression correctly returned exit code 1 and classification
reproduced_freeze. Native job processes, Python services, test profile, and
runtime were cleaned up; the bootstrap log was restored.

Credential-free evidence, relative to this checkout:

- ../../outputs/gameplay-regression-verified.json
- ../../outputs/gameplay-regression-verified/events.jsonl
- ../../outputs/gameplay-baseline-verified.json (passed, exit 0)
- ../../outputs/gameplay-auth.json (passed)
- ../../outputs/gameplay-lobby-authority.json (passed)
- ../../outputs/native-admission-preserved.json (original readiness/admission passed)
- ../../outputs/gameplay-tests.txt (full suite)

The full suite ran 96 tests: 94 passed, two historical rejected experiments
were skipped. This includes the pinned v39 native-instruction emulation
fixtures. New cases cover snapshot envelopes/reassembly, independent client
sequence/ACK state, duplicate frame suppression, incomplete baseline rejection,
and departure classification. A regression test also checks active status
0x22 without the admission-only 0x40 transition bit.

An intermediate verification still used the admission-only bit in its final
joiner check and failed there. That was corrected in the harness, then tested
and rerun; it was not a native reconnect change. The initial discovery probe
also timed out too early during the normal prematch countdown. Final deadlines
cover the observed native timers.

The separate positive --gameplay verification passed at 09:50 Eastern with
20-21 fresh frames per second for each client over all five baseline windows,
zero decoder errors, native phase 6, and complete cleanup. Source-installation
K2/game DLL hashes still match their original stock inputs. Frozen v39
builders and commit f8bd799 are unchanged. No reconnect fix has been attempted.
No manual interaction has been required. All commits remain local.
The original admission-only native scenario also passed independently at
09:51 Eastern, including two native roster identities and full cleanup.

## Resume after interruption

Keep the frozen v39 builders and binaries unchanged. The automated failing
regression now exists. The next investigation can compare native recipient
delivery, host migration, and client identity immediately around creator C3.
Graphical rendering, movement/ability input, deterministic named hero lookup,
and a joiner reconnect recovery control are still outside this verified test.
Hero choice uses the native random-hero command and records the selected IDs.
The creator's wire assignment may be absent because it is the native special
local client; authoritative roster evidence identifies it as client number 0.

## Reproduction

Run from the checkout root.

```powershell
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --gameplay --artifacts .\work\fresh-baseline --report .\work\fresh-baseline.json
py -m thorgor.tools.harness native-match --hon-home 'C:\intelprop\Heroes of Newerth' --creator-disconnect --artifacts .\work\fresh-regression --report .\work\fresh-regression.json
```

All changes and commits remain local. Obtain explicit approval before any
push, publication, or pull request.
