# Reconnect v26: restore gameplay command ownership

> Rejected by live testing: the shared miss fallback was reachable during
> ordinary lobby admission and left player2 as a spectator. V27 adds an
> active-match phase gate before any fallback scan.

V26 preserves the verified v25 behavior: player2 reconnects to the correct
retained player and hero, the host remains connected, and the slave remains
alive. It repairs the remaining command-path mismatch without rekeying or
recreating the native player map.

The live v25 trace showed player2's retained `CPlayer` correctly changing from
native client 1 to fresh client 2. V25 also synchronized the retained hero's
owner field. However, the `CGame` player map was still indexed by the retired
client number. Gameplay handlers look up the command sender in that map before
checking hero ownership, so movement and ability-level packets were discarded.

V26 keeps the normal tree lookup unchanged. Only when that lookup misses, and
only when the map is the singleton game's player map, it scans the retained
players for a `CPlayer+0x6C` client-number match. This resolves the freshly
assigned reconnect transport while leaving every unrelated map untouched. It
does not erase, insert, or move tree nodes, avoiding the iterator and lifetime
failures seen in the rejected v16/v17 experiments.

Install with `INSTALL_RECONNECT_V26.bat` while all HoN clients are closed, then
start a fresh two-client match. Disconnect and relog player2, reconnect, and
verify movement plus ability leveling before repeating the cycle once.
