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
that K2 retains allocation records containing the native client number, account ID,
connection ID, and state byte. Local admission deliberately clears the C0 connection-ID
field before calling this allocator. Restoring that field on a fresh connection proved
unsafe and terminated the dedicated slave during game creation.

The gateway records the native client number in K2's original NETCMD 0x50 response and
marks a C0 as reconnecting only after it has retired that exact authenticated cookie.
For that path it encodes the recorded number in a private connection-ID token. Fresh
admissions retain a zero ID and therefore cannot enter retained-record lookup or steal
a live player's native client number. The explicit reconnect path validates both the
requested retained number and authenticated account. A returning account receives its
original native client number before K2 registers the replacement transport or calls
into game.dll. Internal pseudo clients retain stock allocation behavior.

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
