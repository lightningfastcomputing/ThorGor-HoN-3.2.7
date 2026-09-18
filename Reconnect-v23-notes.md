# Reconnect v23: restored v14 flow baseline

V23 deliberately returns the complete reconnect path to milestone `d08da3a`,
the last build that entered the live match instead of terminating the slave.

- K2 is restored to hash `B0CFEA2ACE1EAF7D7F8CE66C4D8750775A2A18AE22521C47C94EA5A6B4CA375E`.
- game.dll is restored to hash `614EA87B07858531A6F741CB33ED8B9922F5A7D9EA8EE1DC40351437C3A1C01A`.
- The gateway again sends reconnect admission with K2's stock connection-token path.
- All post-v14 allocator and packet-lookup hooks are removed.
- Passive native player-map identity tracing remains enabled.

This is a controlled rollback baseline. Its expected improvement is that a
reconnect reaches the running match without crashing the slave. The known v14
identity-selection defect may still reproduce; the trace will then show the
exact player ordering and identity immediately before selection.

Install with `INSTALL_RECONNECT_V23.bat` while all HoN clients are closed.
