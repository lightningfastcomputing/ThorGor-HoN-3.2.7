# Reconnect v29: gameplay command identity

V29 builds only on the frozen v28 milestone. Player2 still reconnects to the
correct retained player and hero without disconnecting the host or crashing the
slave. Lobby admission remains stock.

The live v28 trace proves why control was missing: player2's retained CPlayer
correctly changed from native client 1 to fresh client 2, but the intentionally
unchanged player map remained keyed by historical client 1. The gameplay packet
dispatcher queried key 2 and discarded movement and ability packets as having
no player before hero authorization could run.

V29 changes only `CGameServer::ProcessGameDataFromClient`. It performs the stock
map lookup first. Only on a miss does it scan retained player values for one whose
live `CPlayer+0x6C` equals the packet sender. It neither changes the shared tree
lookup nor mutates the map, so lobby creation and slot selection cannot use this
fallback.

Native x86 tests execute a normal map hit, the reconnect fallback, and an
unrelated miss. The full test suite passes.

Install with `INSTALL_RECONNECT_V29.bat` while every HoN client is closed. Use a
fresh two-player match, confirm player2 joins a normal lobby slot, then reconnect
player2 and test movement, ability leveling, item commands, and a second reconnect.

## Live milestone result

The first live v29 test crossed the command-control boundary. Player2 rejoined
as the correct retained player without forcing the host out, breaking lobby
slots, or crashing the slave. Movement/control commands did reach the match.

V29 is not complete: immediately after reconnect, assets take roughly three to
five seconds to appear and controls exhibit extreme latency with visible frame
skipping. This suggests that command identity is now correct but the returning
connection is processing a state/replay backlog or receiving an incorrect timing
baseline. Preserve v29 as the control-restored milestone; address timing and
catch-up separately without changing lobby admission, player selection, or the
command-only lookup.
