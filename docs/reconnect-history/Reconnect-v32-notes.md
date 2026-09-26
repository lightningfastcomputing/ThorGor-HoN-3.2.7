# Reconnect v32: client-snapshot identity

V31 proved that the native connected-state repair is correct and stable: the
slave stayed alive, the host remained connected, and player2 rejoined the
correct retained hero. Controls still arrived with a roughly five-second delay.

The slave console exposed the remaining failure directly: every real-time
`ProcessClientSnapshot` packet was rejected as invalid client number 2. At the
same time, the native trace showed player2's retained account, live client
number and connected state were all correct.

Ghidra confirmed that `ProcessClientSnapshot` performs its own player-map lookup
using the historical map key. V32 keeps that stock lookup first. Only on a miss,
it scans retained player values for `CPlayer+0x6c` equal to the packet's fresh
client number. This is scoped solely to client snapshots and matches the safe
fallback already used by the gameplay packet dispatcher.

V32 does not mutate the player map, team roster, lobby, spectator state, host
authority, hero ownership or connection admission. The stable v31 connected-
state transition and complete v29 identity path are unchanged.

All 73 automated tests pass, including native x86 execution for stock snapshot
hits, reconnect snapshot recovery, invalid-client rejection, connected-state
restoration, hero ownership and gameplay dispatch.

Install with `INSTALL_RECONNECT_V32.bat` while every HoN client is closed. The
expected patched `game.dll` SHA-256 is
`D103A500E0ADA6E10F9F15EF8E22C4E5582AD8F7BE50FF109ABDC8E5F9ABBB30`.
