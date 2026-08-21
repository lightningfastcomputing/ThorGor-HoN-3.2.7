# v67 guarded per-client reconciliation — REVERTED (unsafe)

v67 supersedes and safety-reverts v66 after the first gameplay transition
produced an access violation in `cgame.dll + 0x1057C5`.

The crash dump shows an ordinary player entity (type `2`, entity ID `6`) whose
allocation returned null while the client processed its first gameplay
snapshot. The entity registry was therefore incomplete when the snapshot
arrived. v66's periodic reconciliation called the broadcast-only wrapper, which
bypasses K2's connection-state and assigned-client-number readiness checks.

v67 retains the per-client revision comparison needed by a joined client, but
routes periodic updates through the original `QueueStateBlock` entry point.
Dynamic linked-client broadcasts remain unchanged. This restores the two normal
admission guards specifically on the new periodic path.

Verified K2 v67 SHA-256:

`79B6DF5DD59853C8941800C5BAEA9D21FA53FBC2753646E5686551B468FE7E61`

The v66 build is retained only as crash-forensics history and is not selected
by any installer or launcher.
