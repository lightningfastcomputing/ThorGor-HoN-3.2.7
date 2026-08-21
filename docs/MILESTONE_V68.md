# v68 roster-only reconciliation — REVERTED (unsafe)

v68 replaces the reverted v66/v67 experiments with a tightly bounded update
path for the missing non-host picking portraits.

The `15:19:38` session capture shows that the dedicated match process remained
alive while both player clients disconnected together at `15:19:30`, directly
after the picking countdown. No new minidump or HoN Windows Error Reporting
entry was produced. This isolates the failure to the clients consuming the
broad periodic state-block reconciliation during the picking-to-game handoff.

A joined client's initial state transfer identifies blocks `1`, `2`, `13`, and
`14`. The two team hero rosters are blocks `13` and `14`; blocks `1` and `2`
carry broader game/entity state. v68 therefore rejects every block index except
`13` and `14` before entering the per-client revision comparison. The original
queue readiness checks remain in force, and gameplay blocks `1` and `2` cannot
enter the new path.

Verified K2 v68 SHA-256:

`142FCDB10AA866D28100090B3C68597D3C35651230FB40EEFD3C51242F3E1E89`

A subsequent create-game test failed with 13301 unread bits; the dedicated
server closed its manager connection about 14 seconds after the native start-game
command. This proves that even roster-only periodic reconciliation can corrupt the
initial state-transfer packet. v68 is therefore disabled.

v66, v67, and v68 remain in the repository only as crash-forensics history and are
not selected by any installer or launcher.
