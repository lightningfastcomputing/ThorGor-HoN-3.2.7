# Reconnect v28: retained player-entity control

V28 restores the verified v25 boundary before making one reconnect-only change.
The rejected v26/v27 shared player-map fallback is completely absent, so ordinary
second-client admission and lobby slot selection execute the stock code.

Ghidra confirms that `CPlayer::Initialize` stores the connection's client number
in two places: `CPlayer+0x6C` and the retained in-game player entity at
`CPlayer+0x254 -> entity+0x23C`. V25 refreshed the CPlayer and hero owner but left
that player-entity client number stale. V28 refreshes it only after the account-
selected reconnect succeeds, alongside the already verified hero-owner update.

The native x86 emulator verifies that player2's CPlayer, hero, and player entity
all adopt the fresh transport number while the reconnect stack remains balanced.
The full 71-test suite passes.

Install with `INSTALL_RECONNECT_V28.bat` while every HoN client is closed. Start
a fresh two-player match and first confirm player2 can join a normal lobby slot.
Then disconnect and reconnect player2 and test movement and ability leveling.
