# Reconnect v38: keep manager-owned slave alive after creator departure

This candidate preserves the live-proven v32 reconnect and control path for
ordinary joiners. It removes the rejected v35-v37 game-side host-migration and
creator-retention experiments.

Ghidra identified the creator-only shutdown in K2. After the creator's local
transport is removed and game.dll receives its normal removal callback,
`CHostServer` unconditionally queues `StopServer`. V38 bypasses only that
command when `CHostServer+0x2d0` identifies a server-manager-owned dedicated
slave. Unmanaged/local hosts retain the original shutdown behavior.

Automated validation: the 77-test suite passes, including x86 emulation of both
branches. Three obsolete rejected-build assertions are explicitly skipped.

Install with `INSTALL_RECONNECT_V38.bat`.

Expected SHA-256 values:

- `k2.dll`: `CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`
- `game/game.dll`: `D103A500E0ADA6E10F9F15EF8E22C4E5582AD8F7BE50FF109ABDC8E5F9ABBB30`

Live acceptance sequence:

1. Start a fresh two-player match and confirm player2 can disconnect/reconnect.
2. Disconnect the creator while player2 remains in the match.
3. Confirm the slave stays running and player2 keeps receiving game state.
4. Relog the creator and reconnect; confirm the creator returns to the correct
   hero with immediate movement and ability control.
5. If it fails, leave the stack running and close only the HoN clients so the
   compact identity and slave logs remain available.
