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

game.dll retains its verified stock identity predicate at RVA `0x333A3`: compare
`CPlayer + 0x258` with `CClientConnection + 0x0c`. Once that authenticated identity
selects the correct disconnected player, the patch at RVA `0x333DD` skips the obsolete
client-number check and rejoins the stock success path at RVA `0x333FB`. K2 assigns a
new server client number to the replacement transport, so retaining that check produced
`disconnect_client_number_mismatch` even after identity matching was fixed. Returning
the existing CPlayer lets the caller execute `CPlayer::Connected`, which drives the
in-game reconnect notice/timer and state transfer.

The server-capacity patch remains a separate prerequisite so each stage has an exact,
verified input and output hash.

The native match-ID bridge recognizes the stock and capacity-stage hashes. If it
rejects the loaded DLL, the dedicated process keeps
the `0xFFFFFFFF` sentinel. Clients then probe reconnect availability with that invalid
match ID, and the gateway correctly returns zero time remaining, so no reconnect dialog
can appear.
