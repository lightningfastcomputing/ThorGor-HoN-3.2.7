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

game.dll retains both verified stock identity predicates: it compares `CPlayer + 0x258`
with `CClientConnection + 0x0c`, then compares the saved native client number at
`CPlayer + 0x6c` with `CClientConnection + 0x08`.

Ghidra analysis of `CHostServer::GenerateClientID(unsigned short &, int)` established
that K2 already has the native reconnect mechanism. It reuses an earlier client number
when both the C0 connection ID and account identity match its retained allocation
record. The local-admission path parsed the C0 connection ID but then explicitly wrote
zero to `CClientConnection + 0x14`, disabling that lookup. The authority hook now copies
the authenticated C0 connection ID from `[ebp-0x18]` into `CClientConnection + 0x14`
before authentication succeeds. K2 therefore assigns the original client number before
it sends NETCMD 0x50, registers the connection, or calls into game.dll.

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
