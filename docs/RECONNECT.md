# Native reconnect identity

## Current implementation: v39 host continuity after creator departure

The v38 live test was a major boundary: both creator and joiner reconnected to
the correct heroes without killing the slave. Its packet trace also isolated
the remaining freeze. At creator C3, player2 continued sending roughly 30
packets per second, but the slave immediately sent player2 zero packets. After
creator reconnect, output resumed only to the creator.

V39 combines two narrow repairs whose individual behavior is already known:

1. V38 keeps a manager-owned slave alive by suppressing K2's creator-only
   `StopServer` command.
2. The isolated v35 cave repairs only the host-migration player-map miss. It
   reuses the `CPlayer` already being iterated when the fresh live client number
   differs from the retained historical map key. RVA `0x32FB2`, the independent
   ordinary-disconnect target corrupted by v34, remains byte-for-byte stock.

The v36 null-connection shortcut and v37 broad creator-retention patch remain
absent.

Expected v39 hashes:

- K2: `CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`
- game.dll: `0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B`

## Previous implementation: v38 manager-owned creator retention

The v37 live test showed game.dll completing creator removal before the slave
exited roughly 120 ms later. Ghidra then exposed a separate K2 lifecycle rule:
when the removed transport is `CHostServer`'s special local creator at offset
`+0x180`, K2 invokes the game removal callback, frees that connection, and
unconditionally queues the console command `StopServer`.

V38 detours only the `StopServer` construction at K2 RVA `0x2F2E61`. If
`CHostServer+0x2d0` says the slave is owned by the server manager, execution
skips the command and returns through the original cleanup path. Otherwise the
displaced retail instruction runs and local-host shutdown remains unchanged.
The game removal callback and creator transport cleanup still execute.

V38 removes the rejected v35-v37 game-side experiments and restores the
live-proven v32 reconnect image. Expected hashes:

- K2: `CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`
- game.dll: `D103A500E0ADA6E10F9F15EF8E22C4E5582AD8F7BE50FF109ABDC8E5F9ABBB30`

## Previous implementation: v36 host-connection registry fallback

The 2026-09-26 v35 live test used the expected `0DA7FA...` game.dll. Player2
successfully disconnected and reconnected as retained account 3, with live
client number 2. When creator account 2/client 0 disconnected, the slave exited
cleanly and player2 immediately stopped receiving state.

V35 already guarantees a non-null retained CPlayer on the host-migration map
miss. The live player trace proves that candidate's `CPlayer+0x6c` is 2, not
`-1`. The only remaining rejecting successor guard is therefore
`CHostServer::GetClient(2)`, which can return null because K2's connection
registry remains keyed by the historical allocation after reconnect.

V36 detours the complete guard block at RVA `0x32FE1` into cave RVA `0x73DB0`.
A non-null K2 connection resumes the stock path at `0x32FE9`. On only a null
connection result, the cave still requires v35's resolved player and a valid
live number, marks the CPlayer host bit, and resumes stock host-ID assignment
and broadcast at `0x33001`. It never touches `[eax+0xcc]` while EAX is null.
Missing players and invalid live numbers still advance through the stock
candidate loop.

Expected v36 game.dll SHA-256:
`BADCFCCA8A784FBD536FB0849EEA5B614BE41F344EDF9E176D8B498B69F58FA3`.
The 75-test suite executes the null fallback, non-null stock path, rejected
candidate path, v35 map fallback, and preserved ordinary-disconnect target.

## Previous implementation: v35 isolated host-migration successor repair

V35 retains the complete, live-confirmed v32 reconnect and control paths. Live
testing disproved v33's K2-authority theory: reducing the creator's low flags did
not prevent the slave from exiting when the creator left.

The actual failure is in `CGameServer::RemoveClient`. When the departing client
is the current host, the game walks the remaining player records to choose a new
host. For each record it reads the fresh live client number at `CPlayer+0x6c`,
then performs the stock player-map lookup by that number. V32 intentionally
preserves the historical map key while updating `+0x6c` after reconnect, so a
reconnected player2 is present and connected but the lookup misses. Stock code
then rejects that player as a successor and, finding nobody else, shuts down the
match.

V35 changes only that map-miss branch. It reuses the `CPlayer` already being
iterated; the following stock guards still require a live client connection, a
non-null player, and a valid live client number. Admission, team membership,
hero ownership, the shared map, realtime snapshots, and v32 reconnect identity
remain unchanged.

The first inline implementation of this idea, v34, is rejected. Its five-byte
rewrite overlapped the first byte of the independent stock target at RVA
`0x32FB2`. Ordinary player2 disconnection branches directly there, producing
`crash_3.2.7.1_0035.dmp` at 17:44:03 before any reconnect attempt. V35 detours
from RVA `0x32FA3` into an isolated cave and returns to the original hit/miss
destinations. The six stock bytes at `0x32FB2` are hash-checked and executed by
the native regression test.

## Previous implementation: v32 client-snapshot identity

V31 restored the native connected state and remained stable in live testing.
Player2 rejoined the correct hero without evicting the host or crashing the
slave. The remaining five-second control delay produced a definitive native
error for every real-time input snapshot:

`CGameServer::ProcessClientSnapshot() - Received snapshot with invalid client number 2`

The live player-map trace simultaneously showed account 3 retained correctly
with `CPlayer+0x6c == 2` and disconnected bit 0 cleared. Ghidra confirmed
`ProcessClientSnapshot` performs another historical-key lookup before reading
input state. V32 preserves its stock lookup and, only when that lookup misses,
walks retained player values for a unique `CPlayer+0x6c` matching the packet's
live client number. No shared lookup or map mutation is introduced.

## Previous implementation: v31 native connected-state restoration

The v29 milestone is frozen at tag
`reconnect-v29-control-restored-latency-wip`. It proved the reconnecting client
is mapped to the correct retained player and hero and that gameplay commands
reach that player without evicting the host. Its remaining defect was extreme
latency and frame skipping after reconnect.

Live route telemetry isolated that defect. Before disconnect, player2 received
roughly 20--23 game-state packets per second. After reconnect, player2 continued
to send roughly 30--32 packets per second to the slave, but received almost no
normal state deltas and only a roughly 2 KiB catch-up burst every five seconds.
The input path was healthy; the slave still considered the retained CPlayer
disconnected during its per-frame update.

Ghidra confirms why. The server frame loop tests bit 0 of `CPlayer+0x35a`; when
that bit remains set, it skips the normal connected-client update path. The
native `CPlayer::Connected(unsigned int)` implementation performs exactly three
field changes:

1. Clear disconnected bit 0 at `CPlayer+0x35a`.
2. Set connected-transition bit `0x40` at `CPlayer+0x35a`.
3. Set the disconnect deadline at `CPlayer+0x3a4` to `UINT32_MAX`.

V31 mirrors only those changes in the already-proven account-matched reconnect
branch, then continues through v29's identity and hero-owner handoff. It does
not call team methods or mutate team rosters, shared lookup, lobby admission,
host authority, or initial team joining.

V30's team-roster mutation is rejected. Live testing showed that invoking those
methods inside the reconnect callback crashed the slave. It is not accepted by
the runtime verifier and is not part of v31.

## Previous implementation: v29 gameplay command identity

V29 preserves the frozen v28 reconnect route: the returning account selects
the correct retained CPlayer and hero, the host remains connected, and the
slave remains alive. It removes the rejected v26/v27 shared player-map lookup
hook entirely; ordinary lobby admission and slot selection are stock again.

The v28 live trace shows the retained CPlayer correctly adopts fresh client 2,
while its player-map node intentionally remains under historical key 1. The
gameplay packet dispatcher therefore discarded client 2's movement and ability
packets before order authorization. V29 leaves that map and the shared lookup
unchanged. It adds a fallback only inside `CGameServer::ProcessGameDataFromClient`:
after a stock miss, retained player values are scanned for a live `+0x6C` matching
the packet sender. Lobby admission never calls this fallback.

Install with `INSTALL_RECONNECT_V39.bat`. Expected game.dll SHA-256:
`0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B`.
Expected K2 SHA-256:
`CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`.

Live acceptance remains required: verify player2 reconnect once, then disconnect
and reconnect the creator while player2 remains in the running match.

The first v29 live test confirmed that player2's commands now reach the correct
retained hero and the host remains connected. Remaining defect: the returning
client initially lacks assets for roughly three to five seconds, then processes
controls with extreme latency and frame skipping. V29 is frozen as the first
correct-player, control-restored milestone; subsequent work must isolate the
reconnect timing/catch-up path without broadening the command lookup.

## Historical v22 analysis

The September 18 v21 test produced `crash_3.2.7.1_0032.dmp` at the same native
string comparison. The identity snapshots immediately before the crash were
correct: account 2/client 0 remained the host and account 3/client 1 remained
player2. Dump reconstruction shows the first lookup record was the live host,
not the disconnected player2. Its token was zero, the incoming reconnect token
was `0x8001`, and its address string was already unsafe. Native lookup checked
the address before checking the token even though both had to match.

V22 performs the equivalent predicate in a safe order: token mismatch skips the
record immediately, state zero skips it next, and only a matching live transport
reaches the original address comparison. This prevents unrelated host and old
player transports from exposing stale strings during a reconnect probe.

The September 17 v20 live reconnect reached the slave but crashed it before C0
admission. The matching minidump reports the C++ exception `invalid string
position` at `k2.dll + 0x78A6`, called from `+0x70D50D` and ReadPackets at
`+0x2F5DC2`. Ghidra confirms that native connection lookup compared the incoming
address against `CClientConnection+0x1AC` before checking transport state.
Disconnected transports remain linked for reconnect-number reclamation, but
their address string has already been destroyed.

V21 skips state-zero transports at `+0x70D4EA`, before the string comparison.
Live transports execute the displaced instructions and the rest of native
lookup unchanged. The patch therefore fixes the observed pre-admission crash
without changing account selection, player-map ownership, team, hero, or state
delivery. The native bridge also records the server's player map in selector
order whenever it changes, including client number, account ID, connection
state, and flags. This diagnostic is read-only.

The September 17 v19 crash dump (`crash_3.2.7.1_0029.dmp`, 11:39:30) places
the access violation at `k2.dll + 0x286B2B`, inside CPacket::ReadInt, reached from
`+0x2F8C26` and the C0 admission call at `+0x2F5ADE`. The hook at `+0x2F5AD6`
clobbered EDX, which held the packet pointer. It replaced it with the client
allocation address from `[ebp-0x18]`; ReadInt then treated client number `-1`
as a vtable and read address `0x4f`. The failure preceded GenerateClientID.

Two native stack-lifetime mistakes also corrupted identity:

- `[ebp-0x18]` starts as the parsed connection token, but is reused by version
  parsing and then by the client allocation at `+0x2F59D6`.
- `[ebp-0x48]` starts as the account ID, but overlaps the bool result of the
  map insertion whose output begins at `[ebp-0x4c]`. First admissions can thus
  store native account `0x80000001` for different authenticated players. This
  explains how an account-based reconnect search could select the host.

V20/V21 reserve eight private stack bytes and capture both parsed values at
`+0x2F555C`, before either local is reused. The later authority hook preserves
all registers, including EDX, and copies the saved account into the connection.
The private reconnect marker is removed before game.dll sees the identity.

Initial admissions retain stock zero-token allocation. For a reconnect the
gateway encodes the observed original native number as `0x8000 | number`.
The local AuthSuccess allocator wrapper verifies the **full** allocation-record
number and authenticated account, then checks every linked CClientConnection.
Reclaim is permitted only when any matching transport has state zero and the
same account. An active or mismatched transport prevents reclaim, with no
partial mutation. Failed reclaim clears the private token and falls back to
stock fresh allocation, allowing the stock game identity check to reject a
number mismatch instead of stealing another player's connection.

Allocation-record byte `+0x0a` is initialized from `token == 0`; it is **not** an
active/inactive flag. V19's assumption about this field was wrong. ThorGor's
multiplayer patch also retains disconnected transports in the linked list.
After validating the complete list, V21 sets only those retired transports'
client-number fields to `-1`, so native lookup and targeted delivery find the
replacement connection. The allocation record, retained CPlayer, player-map
key, team, and hero remain unchanged. GenerateClientID itself remains stock.

The gateway retains the reconnect decision across C0 retransmissions, rotates
transport even when the public UDP endpoint is reused, and recognizes the
creator's `69 01` prefix before client assignment `50`. This allows client
number zero to be captured too.

### Historical v22 installation notes

The former `INSTALL_RECONNECT_V22.bat` wrapper was removed during the v39 root
cleanup. Numbered wrappers always applied the manifest currently checked out;
they were not reproducible rollback packages. Restore the corresponding Git
revision or tag when reproducing a historical build. A new match is required
after changing native patches because existing player objects retain the prior
build's identity state.

Expected K2 SHA-256:
`A4F9856A53A01D212CAE03EA1746F6594904F8D255956AD6D849ABD467281A77`

Expected game.dll SHA-256 (unchanged capacity patch):
`929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B`

Run the tests with Python, unicorn and pefile installed and
`THORGOR_TEST_HON_HOME` set to a game installation containing the stock DLL
backups. The native suite builds patched copies in temporary directories;
it does not alter the installed game. Tests execute the actual x86 capture,
authority hook, allocator wrapper, native connection lookup, and stock game
identity predicates. The game predicate test models the unrelated empty-string
constructor because its CRT imports are not linked in the emulator.

Live acceptance is still required: start two players, leave as player2 during
an active match, reconnect, verify each player's hero/team/control, and continue
playing beyond the earlier delayed-crash window. Repeat the leave/reconnect,
then test the creator leaving and returning. Unit/native emulation success is
not an end-to-end live-match result.

## Historical experiments

The entries below describe earlier attempts and their then-current assumptions.
The v22 analysis above supersedes the inactive-record and persistent-token claims.

## v14 flow milestone

The 2026-09-16 two-client test established the first stable end-to-end reconnect flow:
the reconnect dialog appeared, the returning client entered the running game, and the
slave remained alive. This is preserved by the Git tag
`reconnect-v14-flow-milestone`.

The remaining defect is player ownership. A disconnected `player2` returned as
`player`, disrupting the match. The transport handoff is therefore stable enough to
reach game admission, but the retained `CPlayer` selection or final ownership binding
still resolves to the creator instead of the authenticated returning account. Do not
describe v14 as a complete reconnect implementation.

## v15 rejected native-number reuse

The follow-up log and Ghidra analysis located the mismatch before game admission:
player2 originally held K2 client number 1, but reconnect was freshly assigned number
2. v15 attempted to reclaim number 1 inside `CHostServer::GenerateClientID`. The live
test proved this unsafe: K2 still owned number 1, the duplicate registration killed the
slave, and game.dll was never reached. That experiment is retained only in Git history.

## v16 atomic player-map transfer

Build v16 restores the stable v14 K2 admission behavior and replaces the incomplete
single-field game patch with a native map rekey. The implementation is hash-pinned to
the capacity-patched 3.2.7.1 game.dll and uses a verified executable padding cave. The
instruction-level test executes the real patched bytes and verifies the erase, insert,
player pointer, player number, register state, and stack state. The full suite contains
69 passing tests, including 9 tests executing the patched x86 DLL instructions.

The first live v16 test exposed one additional native lifetime requirement. Although
the map was rekeyed, the surrounding reconnect function still held the erased tree node
in EBX and later loaded `CPlayer *` through that freed node. This produced the apparent
host/player2 ownership swap, ended the host's match, and crashed the slave roughly 17
seconds after admission.

## v17 live iterator transfer

Build v17 also replaces the reconnect function's saved EBX iterator with the new tree
node returned by `map::operator[]` (`mapped-value address - 0x10`). The stock success
path therefore resolves the retained player through the live replacement node. The
native emulation test now asserts this iterator transfer in addition to the map key,
mapped player pointer, player number, register state, and stack state.

The following live test proved that even a structurally valid map rekey was the wrong
layer: player2 inherited the host's hero, the host received a defeat result, and the
slave terminated. v17 remains historical evidence only.

## v18 stock persistent-token reconnect

Build v18 removes the game-side identity mutation entirely. It uses the stock K2
inactive-record lookup with one authenticated token that exists before the initial
allocation and survives the proxy route change. This preserves player2's native number,
player-map key, team membership, selected hero, and host ownership as one identity.

Live testing rejected that design: a nonzero token during the special local initial
admission crashed the slave before K2 assigned the creator a native client number.

## v19 retired-native-number reconnect

Build v19 restores the proven stock initial admission. After K2 reports the assigned
native client number, the gateway retains it with the authenticated cookie. A returning
client receives an authenticated private token whose low byte names that exact native
number. K2 still requires the record to be inactive and the account identity to match;
only the stock token comparison is replaced by the exact native-number comparison.
This prevents a reconnect for player2 from selecting the active host/player record.
