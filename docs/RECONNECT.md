# Native reconnect identity

## Current implementation: v22 candidate

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

### Installation and validation

Run `INSTALL_RECONNECT_V22.bat` from this checkout. It resolves its own location,
uses Python on PATH and HON_HOME (or the normal installed game directory),
stops the existing stack, installs and verifies the patches, resets volatile
state, and launches this checkout's dashboard. Older numbered launchers remain
historical and may reference the previous workspace. Start a **new match**;
old native player objects already contain the previous build's corrupt account
identity and cannot be repaired by changing the gateway alone.

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
