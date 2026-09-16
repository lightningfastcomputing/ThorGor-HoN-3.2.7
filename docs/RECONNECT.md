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

game.dll retains both verified stock predicates: it compares `CPlayer + 0x258` with
`CClientConnection + 0x0c`, then `CPlayer + 0x6c` with
`CClientConnection + 0x08`. The reconnect admission must therefore restore the old
native client number before game.dll performs those checks.

Ghidra analysis of `CHostServer::GenerateClientID(unsigned short &, int)` established
that this allocator runs before `game.dll` receives the connection. Its retained record
contains the native client number, account ID, C0 connection ID, and connection state.
When the connection ID is nonzero, stock K2 matches the disconnected record by that ID
and account, then returns the record's original native client number.

Normal admission leaves K2's persistent connection field cleared exactly as the retail
local path expects. On reconnect only, the gateway encodes the previously observed
native client number in a private connection token. The authenticated K2 hook exposes
that token to `GenerateClientID`, which locates and returns the retained allocation by
client number. It does not trust the client-supplied token or affect fresh admissions.

Only a route that the authenticated gateway has retired is marked as reconnecting. The
gateway uses a private account marker which K2 removes before game admission. Live v14
evidence showed the allocation record does survive: a returning player2 received fresh
number 2 while number 1 remained reserved. v15 reclaims number 1 inside K2, preserving
the retained CPlayer and the `IGame + 0xfc` player-map key together.

Changing either identity later inside game.dll was unsafe: K2 had already registered
the new number, while the player map remained keyed by the old one. That produced the
wrong local player, black pre-match shells, and slave instability. The v14 game-layer
number mutation has been removed.

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

## v15 native-number reuse

The follow-up log and Ghidra analysis located the mismatch before game admission:
player2 originally held K2 client number 1, but reconnect was freshly assigned number
2. v15 supplies the retained number only on an authenticated retired route and patches
`CHostServer::GenerateClientID` to return that existing allocation. game.dll is restored
to its stock account-and-number checks, avoiding any post-registration identity rewrite.
