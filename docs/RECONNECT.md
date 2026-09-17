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

The gateway also assigns a stable nonzero uint16 connection token to each authenticated
cookie. A private account marker tells the K2 hook that this token is gateway-owned;
K2 copies it into `CClientConnection + 0x14` and removes the marker before game.dll sees
the account. The same token is sent on the initial admission and reconnect.

Ghidra analysis of `CHostServer::GenerateClientID(unsigned short &, int)` established
the retail reconnect contract. Its 12-byte allocation record contains the native client
number, account ID, uint16 connection token, and active flag. A nonzero token searches
only inactive records; if both token and account match, stock K2 returns the original
native client number. Otherwise it allocates normally and stores the token for later.

game.dll is therefore left on its verified stock account-and-number predicates. No
`CPlayer`, player-map, team, or hero ownership field is changed during reconnect.

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

The following live test proved that even a structurally valid map rekey was the wrong
layer: player2 inherited the host's hero, the host received a defeat result, and the
slave terminated. v17 remains historical evidence only.

## v18 stock persistent-token reconnect

Build v18 removes the game-side identity mutation entirely. It uses the stock K2
inactive-record lookup with one authenticated token that exists before the initial
allocation and survives the proxy route change. This preserves player2's native number,
player-map key, team membership, selected hero, and host ownership as one identity.
