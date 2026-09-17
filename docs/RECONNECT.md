# Native reconnect identity

HoN 3.2.7.1 normally locates a disconnected player by the retail account ID stored in
`CPlayer + 0x258`, then verifies the native client number at `CPlayer + 0x6c` against
`CClientConnection + 0x08`.

The local authentication path used to clear that account field: every player was
recorded with account ID zero. Matching on the gateway's C0 connection ID was also
incorrect because that value is not the server-assigned client number stored in
`CPlayer + 0x6c`; the search skipped every player and returned
`disconnect_game_in_progress`.

The gateway now rewrites the authenticated account into a stable local-only native
identity (`0x80000000 | account_id`). Interpreted as `int32` it is negative, so the
retail profile/avatar path continues treating the player as local and does not replace
lobby portraits with the Chiprel fallback. The K2 admission patch preserves this value
in `CClientConnection + 0x0c` and no longer clears it before CPlayer initialization.
Both the initial connection and the returning C0 receive the same value.

game.dll retains the verified account predicate: it compares `CPlayer + 0x258` with
`CClientConnection + 0x0c`. Once that selects the retained player, the v16 reconnect
hook transfers the player to K2's freshly allocated client number before entering the
stock success path.

Ghidra analysis of `CHostServer::GenerateClientID(unsigned short &, int)` established
that this allocator runs before `game.dll` receives the connection. Forcing it to return
the disconnected player's still-registered number creates two K2 connection objects for
one transport ID. The live v15 test confirmed that collision terminates the slave before
game.dll receives a reconnect packet. K2 therefore remains on its stock fresh-allocation
path for every admission.

Only a route that the authenticated gateway has retired is marked as reconnecting. The
gateway uses a private account marker which K2 removes before game admission. Live v14
evidence showed the allocation record survives: returning player2 received fresh number
2 while retained player2 and the `IGame + 0xfc` map entry remained number 1.

Changing only `CPlayer + 0x6c` was incomplete because the native player map remained
keyed by the old number. v16 uses the game's own iterator, range-erase, and map-insert
routines to atomically remove the old node, insert the same retained `CPlayer *` under
the fresh number, and then update `CPlayer + 0x6c`. This keeps K2 transport identity,
game lookup identity, and local player ownership synchronized.

The server-capacity patch remains a separate prerequisite so each stage has an exact,
verified input and output hash.

The native match-ID bridge recognizes the stock and capacity-stage hashes. If it
rejects the loaded DLL, the dedicated process keeps
the `0xFFFFFFFF` sentinel. Clients then probe reconnect availability with that invalid
match ID, and the gateway correctly returns zero time remaining, so no reconnect dialog
can appear.

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
