# Reconnect v37: retain an active disconnected creator

The v36 live test at 11:15 on 2026-09-26 disproved the host-successor-only
diagnosis. The slave reset its manager connection roughly 120 ms after creator
client 0 departed, while player2 was still sending normally.

Ghidra shows an earlier creator-only branch in `CGameServer::RemoveClient`.
After marking the player disconnected, stock code retains an active ordinary
player whose `CPlayer+0x7c` is `-1`, but host flag `CPlayer+0x35c & 0x04` forces
the creator through permanent player removal, client-ID release, team/map
removal, and host migration. V37 removes only that host-flag override. Lobby
and spectator departures remain stock. An active creator now remains in the
same reconnect grace lifecycle already proven for player2.

V32 through v36 reconnect identity, connected-state, snapshot, and command
fallbacks are unchanged. Install with `INSTALL_RECONNECT_V37.bat`.

Expected game.dll SHA-256:
`C3EF2BD3AFCBD05EE3FB05AEFBF13E94EF7F5FEEC266803CD81EC896E63BE87F`.
