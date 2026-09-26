# Reconnect v39: preserve joiner state after creator departure

V38 proved that both creator and joiner can reconnect correctly and that K2 no
longer terminates the manager-owned slave. The preserved packet trace exposed a
separate host-continuity failure: immediately after creator C3, player2 kept
sending about 30 packets per second but received zero packets from the slave.
Creator reconnect restored output only to the creator.

V39 retains v38's narrow K2 `StopServer` suppression and adds only the isolated
v35 host-successor lookup repair. During host migration, a successfully
reconnected player's fresh client number may differ from the historical player
map key. On only that lookup miss, the patch reuses the valid `CPlayer` already
being iterated and continues through the stock successor guards.

The unsafe v34 overlapping patch, v36 null-connection shortcut, and v37 broad
creator-retention patch are absent. The ordinary-disconnect branch target at
game.dll RVA `0x32FB2` remains stock and is executed by the native regression
test.

The 77-test suite passes with two rejected historical experiments skipped.

Expected SHA-256 values:

- `k2.dll`: `CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`
- `game/game.dll`: `0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B`

Install with `INSTALL_RECONNECT_V39.bat`, then start a fresh match. Confirm
player2 receives continuous state while the creator is disconnected before
testing creator reconnect.

## Frozen live result — 2026-09-26

V39 is frozen as a major reconnect milestone. Live two-client testing proved:

- The joiner can disconnect and reconnect to the correct hero with controls.
- The creator can disconnect and reconnect to the correct hero with controls.
- Joiner departure does not interrupt the creator's game.
- Creator departure no longer terminates the slave or match.
- While the creator is absent, the joiner's existing connection stops receiving
  live state and appears frozen.
- If that joiner disconnects and reconnects, their connection is re-established
  and the frozen state clears.

The remaining defect is therefore limited to keeping an already-connected
joiner subscribed to state across creator departure. Do not redesign reconnect
identity or remove the v38 K2 lifecycle patch when continuing from this point.
