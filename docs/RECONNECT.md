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
selects the correct disconnected player, the patch at RVA `0x333DD` copies the saved
`CPlayer + 0x6c` client number into the replacement `CClientConnection + 0x08`, then
rejoins the stock success path at RVA `0x333FB`. K2 initially assigns each replacement
transport a fresh number. Merely bypassing the mismatch check made the slave send and
the client acknowledge the snapshot, but the client stayed in a black pre-match shell
because the snapshot's saved player number and the new connection number differed.
Adopting the original number before the connection response keeps transport identity,
`CPlayer::Connected`, the reconnect notice/timer, and state transfer aligned.

The server-capacity patch remains a separate prerequisite so each stage has an exact,
verified input and output hash.

The native match-ID bridge recognizes the stock and capacity-stage hashes. If it
rejects the loaded DLL, the dedicated process keeps
the `0xFFFFFFFF` sentinel. Clients then probe reconnect availability with that invalid
match ID, and the gateway correctly returns zero time remaining, so no reconnect dialog
can appear.
