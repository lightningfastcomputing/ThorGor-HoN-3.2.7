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
`CClientConnection + 0x0c`. Once that selects the correct disconnected player, the
handoff copies K2's authoritative new transport number from `CClientConnection + 0x08`
into `CPlayer + 0x6c` before entering the stock reconnect-success path.

Ghidra analysis of `CHostServer::GenerateClientID(unsigned short &, int)` established
that this allocator runs before `game.dll` receives the connection. Its retained record
contains the native client number, account ID, C0 connection ID, and connection state.
When the connection ID is nonzero, stock K2 matches the disconnected record by that ID
and account, then returns the record's original native client number.

Normal admission leaves K2's persistent connection field cleared exactly as the retail
local path expects. Temporary handshake IDs are forwarded but never copied into the
player record; doing so terminated the slave during server selection or game creation.

Only a route that the authenticated gateway has retired is marked as reconnecting. The
gateway uses a private account marker which K2 removes before game admission. K2 keeps
its stock fresh-client allocation because the disconnected transport allocation record
does not survive; game.dll then transfers that new number into the retained player.

Changing `CClientConnection + 0x08` later inside game.dll was unsafe: K2 had already
registered the new number, producing split transport/player identity, the black
pre-match shell, and slave instability. That experiment has been removed.

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
