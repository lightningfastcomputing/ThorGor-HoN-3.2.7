# Native reconnect identity

HoN 3.2.7.1 normally locates a disconnected player by the retail account ID stored in
`CPlayer + 0x258`, then verifies the native client number at `CPlayer + 0x6c` against
`CClientConnection + 0x08`.

The local authentication path does not populate the retail account field: every player
is recorded with account ID zero. During reconnect, the stock search therefore selects
the first player in the match (normally the host) and emits
`disconnect_client_number_mismatch` before it can reach the returning player's record.

The reconnect patch changes only the search predicate at game.dll RVA `0x333A3`. It
uses the native client number, which the gateway keeps stable for the lifetime of a
match, to select the correct player record. Profile/account fields are not synthesized
or changed; this is important because doing so corrupts lobby icons and other profile
presentation state.

The server-capacity patch remains a separate prerequisite so each stage has an exact,
verified input and output hash.

The native match-ID bridge must recognize the final patched hash as well as the stock
and capacity-stage hashes. If it rejects the loaded DLL, the dedicated process keeps
the `0xFFFFFFFF` sentinel. Clients then probe reconnect availability with that invalid
match ID, and the gateway correctly returns zero time remaining, so no reconnect dialog
can appear.
