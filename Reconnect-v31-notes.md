# Reconnect v31: native connected-state restoration

V29 remains frozen at tag `reconnect-v29-control-restored-latency-wip` and is
the rollback point. It reconnects player2 to the correct retained hero without
crashing the slave or evicting the host, and gameplay commands reach that hero.

The remaining v29 symptom was severe latency and frame skipping. Packet traces
showed that player2 continued sending normally after reconnect, while the slave
sent only periodic catch-up bursts instead of its normal per-frame stream.

Ghidra analysis found the precise missing state transition. The server frame
loop skips its connected-client path while bit 0 of `CPlayer+0x35a` is set.
Native `CPlayer::Connected` clears that bit, sets bit `0x40`, and resets the
disconnect deadline at `CPlayer+0x3a4` to `UINT32_MAX`.

V31 preserves the complete v29 identity, hero ownership and gameplay command
path. It mirrors only those three native field writes in the successful
account-matched reconnect branch. It does not alter the player map, team roster,
lobby behavior, spectator handling, host authority, or initial team selection.

V30 is rejected because its reconnect-time team method calls crashed the slave.
Its hash is intentionally absent from the supported-binary verifier.

All 72 automated tests pass, including native x86 execution proving that v31
restores connected state while retaining player2's correct client, hero and
player-entity ownership.

Install with `INSTALL_RECONNECT_V31.bat` while every HoN client is closed. The
expected patched `game.dll` SHA-256 is
`36D20B56BFDB7B1B4988BCA5727B1AECB928979575DB59FBF38698CB63C3916C`.
