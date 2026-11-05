# Autonomous development progress

## Graphically verified reconnect milestone

On November 5, 2026, the user confirmed in the graphical HoN clients that
host departure no longer freezes the other player and that both roles can
select a hero after reconnecting. This freezes the behavior tested at
`a2d49ea` with the `selection-recovery` build. The automated countdown and
active-play regressions also passed. The unit suite recorded 119 passes and
two historical skips.

## Countdown continuity and repaired launcher

Both follow-up graphical bundles, 13:30:37 and 13:33:25 on November 5,
recorded `native_variant: v39` and the Program Files installation. The last
slave loaded the frozen game.dll hash. At 13:32:59 its creator sent C3, and the
joiner's inbound rate dropped from about 20 packets per second to zero despite
continued sends.

`START_SELECTION_RECOVERY.bat` selects the workspace copy and the repaired
variant in both server and client mode. Its verification command passed even
when the shell pointed at Program Files and v39. The dashboard displays the
variant next to the LAN address. This keeps the manual test on the build whose
results it is meant to verify.

The unpicked selection test now disconnects the creator first and checks the
joiner's same connection for 15 seconds before reconnect. Frozen v39 delivered
zero snapshots during all 15 windows while the native phase 3 clock advanced
(`work/selection-countdown-v39.json`). The repaired slave delivered 304 fresh
snapshots, with 20 or 21 per window, and both players chose heroes after
reconnecting. Both heroes spawned in phase 6. A second creator departure
left the joiner receiving 303 fresh snapshots over 15 seconds. The repaired
run passed and cleaned up (`work/selection-countdown-repaired.json`).
The user subsequently confirmed the graphical countdown and hero picker
on this build.
Unit suite result: 119 passed and two historical skips.

## November 5 graphical report and native reproduction

The debug archive contained the repaired 12:39 launch and a later frozen v39
launch. The latter reproduced zero inbound packets for the joiner after the
creator's C3. The repaired launch did not contain the same departure sequence.
The dashboard now includes the current variant in new debug ZIP metadata and
timestamps each health-check block.

The new `--pick-after-reconnect` gate exercises both roles before their first
hero pick. `unpicked-reconnect-repaired-1.json` exposed the missing creator
assignment from a combined 69 01 / 50 reliable packet. With that parser
corrected, `unpicked-reconnect-repaired-2.json` reproduced the native hero
selection failure. Both players resumed fresh snapshots but neither pick
changed selected hero from 0xFFFF.

`unpicked-selection-fix-1.json` verified the first candidate's random picks
after reconnect and both native heroes spawning in phase 6. A second creator
departure then failed the disconnected-bit check. The joiner still received
about 20 packets per second. Disassembly traced this to a third historical-key
lookup in RemoveClient, so the final candidate also resolves that lookup for
already started matches. See `docs/RECONNECT.md` for details.

The final `selection-recovery` candidate passed
`work/unpicked-selection-direct.json`. Both unpicked roles reconnected with
their retained player records and selected specific hero types through C8 06.
Both heroes spawned in phase 6. The returning creator's subsequent C3 marked
their player disconnected. The joiner received 304 fresh snapshots in 15
seconds, with 20 or 21 per window and the same native connection and match.
The run cleaned up the native job and restored the shared console log.

Authentication and lobby-authority scenarios passed. The full unit suite ran
121 tests with 119 passes and two historical skips, including instruction
emulation of both hero-pick hooks and the phase-bounded removal fallback.
The manual copy was upgraded and verified with the new variant. Graphical
hero selection and the main-menu overlay still need a manual retest.

## Manual repaired-build launch

The installer and dashboard now honor the explicit environment setting
`THORGOR_NATIVE_VARIANT=registry-continuity`; absence still selects frozen v39.
The same choice applies to remote-client setup. Installation preserves a
verified v39 backup and supports restoring it when v39 is selected again.
The harness's independent explicit native-variant selection is unchanged.

A complete separate manual-test game copy is prepared at
`work/manual-test/Heroes of Newerth`. Supported patch installation and CLI
verification passed there with K2 hash `98138B1086092558...`. The original game
installation was not modified. See `docs/MANUAL_TEST.md` for two-shell startup,
accounts, two graphical clients, the creator-departure checklist, and shutdown.
No graphical stack or clients were launched during this preparation; visual
movement and creator rejoin still require their own verification. The normal
stack's completion observer remains disabled by default.

An initial preparation attempt hit the restricted default temporary directory;
retrying with workspace TMP/TEMP succeeded. The first new rollback test caught
that old K2 rebuilding cannot always recover v39 from the repaired binary;
restoration now requires and uses the exact preserved v39 backup instead.
Final verification: 120 unit tests ran, 118 passed, two historical checks skipped.
Reinstalling the selected repair was idempotent, and CLI verification passed
again. Tests cover exact repaired output, unchanged v39 backup, idempotence,
restoration, default selection, and rejection of an unknown variant.

## Latest outcome: selection recovery and repeated native matches

Local verified milestones: b43aa8b (registry repair) and 3e6eb25 (active-match
snapshot recovery). Subsequent selection/lifecycle changes are verified and
being committed as the next local milestone.

- selection-recovery-1.json passed both joiner and creator reconnect during
  hero selection. Their chosen heroes and teams survived, and the same match
  then reached active phase 6 with both snapshot streams.
- termination-1.json passed the native C6 EndMatch 1 command, authoritative
  phase 7, the 21-second end countdown, and native game-context clearing while
  the manager/slave survived.
- repeat-matches-1.json exposed a second lifecycle defect: native context was
  cleared, but backend match_id stayed 1 and next creator authority was denied.
  Genuine control traffic still contained only association/wake, without a
  native completion/status notification.
- repeat-matches-4.json passed two complete matches on the same slave PID
  29184 and the same manager/backend. Match IDs 1 and 2 were independently
  allocated. Round 2 began in phase 1 with no selected/spawned heroes, then
  reached phase 6 with both streams. Both rounds ended and cleared natively.

The completion observer requires a verified native phase 7 followed by clearing
of that same CGame's context, with the same PID, match ID, and authenticated
server/manager session. Its new backend notification clears only that match's
ownership and reconnect records; stale/wrong-session requests cannot clear a
newer match. The harness registers a session before admission when the hybrid
manager flow has none. The normal installer and stack defaults remain frozen;
--complete-matches is an opt-in observer capability exercised by lifecycle tests.

The first observer probe had no registered session and correctly failed to
release backend ownership. A later registration probe exposed the HTTP helper's
argument-name collision with the protocol's port field; that was corrected
and tested. Failed probes remain in the evidence directory. No failing candidate
was labeled a successful repeat-match test.

Movement remains blocked and is exposed by --movement: movement-1.json verified
both native hero pointers, types, owners, and world coordinates, then failed
with native_control_selection_missing. Both control-selection sets were empty.
The old source's C8 40 selection command is unsupported in the 3.2.7.1 dispatch
table. Native C7 serializes a 32-bit frame ACK followed by input entity snapshots
(CClientSnapshot::WriteBuffer at K2 379980, 78-byte internal entity entries).
The required control-selection input entity/schema has not been recovered from
the available older source and preserved traces. Sending position commands
without that selection cannot establish movement. No selection-memory writes,
fabricated state packets, rendering claims, or untested control claims were used.

All evidence above is under ../../outputs/creator-freeze-session/. Final full
suite: 118 run, 116 passed, two historical skips (final-suite.txt). Auth,
lobby-authority, original frozen native admission, and a fourth repaired
creator-departure check were re-executed before the next local commit.
Resume with the input-entity encoding or an independently isolated native-client
input capture; the creator freeze, retained-hero snapshot recovery, selection
recovery, and two-match lifecycle have already been exercised unattended.

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
