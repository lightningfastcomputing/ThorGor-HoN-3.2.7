# Reconnect v25: restore retained hero control

V25 is a narrow continuation of the frozen v24 correct-player milestone. It
does not change account selection, K2 allocation, reconnect routing, the native
player map, team/slot assignment, or host ownership.

Reverse engineering of HoN 3.2.7.1 identified the remaining authorization
mismatch:

- `CPlayer::Initialize` stores the native client number at `CPlayer+0x6C`;
- `CPlayer::AssignHero` copies that number to `IHeroEntity+0x444`;
- `IUnitEntity::CanReceiveOrdersFrom` first compares the command sender against
  `IUnitEntity+0x444` and rejects the order when they differ.

On the verified v24 flow, player2's retained CPlayer changes from native client
1 to freshly allocated client 2. The retained hero still contains owner 1, so
the reconnect succeeds visually but player2 cannot issue orders.

V25 keeps the v24 CPlayer update and then uses HoN's entity registry plus its
native hero cast to locate the already-assigned hero. Only after both guarded
lookups succeed does it update `IHeroEntity+0x444` to the fresh client number.
The hook returns to the unchanged v24 reconnect-success path. A missing or stale
hero safely skips the ownership write and still completes reconnect.

Install with `INSTALL_RECONNECT_V25.bat` while all HoN clients are closed.
