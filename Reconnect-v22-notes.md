# Reconnect v22 test build

V21 proved that reconnect identity remained correct immediately before the
slave crash, but the transport lookup still compared the incoming address with
the live host's stale address string. V22 checks the uint16 transport token
first. The host token (`0`) cannot match player2's reconnect token (`0x8001`),
so that record is rejected without touching its string. State-zero records are
also skipped before the original address comparison.

Run `INSTALL_RECONNECT_V22.bat` and create a fresh two-player match.

Expected patched hashes:

- `k2.dll`: `A4F9856A53A01D212CAE03EA1746F6594904F8D255956AD6D849ABD467281A77`
- `game.dll`: `929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B`
