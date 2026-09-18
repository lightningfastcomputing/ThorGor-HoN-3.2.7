# Reconnect v21 test build

V21 addresses the exact v20 slave crash observed during reconnect. The crash
was an uncaught `invalid string position` exception caused by native packet
lookup comparing an incoming address against a disconnected transport whose
address string had already been destroyed. V21 skips that retired transport
before the comparison and leaves live transport lookup unchanged.

Run `INSTALL_RECONNECT_V21.bat`, create a fresh two-player match, disconnect
and log out `player2`, log back in as `player2`, then press Reconnect.

Expected patched hashes:

- `k2.dll`: `BA40A63B4F0AA20A93C058A08699A10F9BE3A46CC10AB4DC702AF9C0A79CF5BD`
- `game.dll`: `929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B`

If reconnect is still wrong, leave the stack open after the test. The read-only
native player snapshots are written to
`var/work/reconnect_identity_events.jsonl`, alongside the normal gateway and
manager logs. These snapshots identify the first point where account 3/client
1 changes or is selected incorrectly without modifying live player state.

Verification: all 84 tests pass, including 22 native x86 execution tests against
the exact supported HoN DLL fixtures and a v20-to-v21 upgrade test.
