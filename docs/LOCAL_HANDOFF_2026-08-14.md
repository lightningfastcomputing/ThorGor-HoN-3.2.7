# ThorGor local handoff — 2026-08-14

## Scope and repository state

- Local working copy: `C:\intelprop\thorgor archive`
- Branch: `main`
- Remote: `https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git`
- No commit or push was made. GitHub was not modified.
- The local worktree is intentionally dirty and contains all milestone work.
- All ThorGor and HoN test processes were closed before this handoff.

## Current safe installed state

- `k2.dll` is restored to stable v65:
  `82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB`
- `game\cgame.dll` remains v61:
  `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`
- `ThorGorMasterServer.exe` remains v71:
  `B7A0C8F1A061EF8144D66A6E938AC62CF150AE4DFBCC90F81241B5485FD2EE43`
- `ThorGorManagerBridge.exe` remains v70:
  `ABF0334688C1BEE10DFBA14F83C33751B0B0C80CBE6842261840DA71450A4B92`
- The active launcher is restored to `v71 Stable K2` and invokes
  `PATCH_K2_V65.ps1`.
- Full regression suite after rollback: 68 tests passed.

## What works

- Two accounts authenticate and chat.
- A dedicated slave registers and publishes a hosted game.
- A second client can discover and join the lobby.
- Player names and slots synchronize to both clients.
- The host sees the complete hero grid during picking.
- The v71 master server returns the same nine-section, 231-byte legacy product
  catalog to both clients.

## Remaining bug

The joined/non-host client reaches the picking phase but displays only gray
hero placeholders. The host sees the hero portraits and can inspect heroes.

## Important conclusions

1. Do not retry or inject K2 state blocks to solve this bug.
2. v72 used an unsafe queue wrapper and caused the dedicated slave/client
   stream to fail with `13301 unread bits`.
3. v73 restored K2's original readiness guards but failed with the identical
   `13301 unread bits` result. The entire periodic reconciliation approach is
   rejected, not merely its guard choice.
4. v72 and v73 were removed from the active local repository and launcher.
5. The earlier block 3–8 inference came from a shared `console.log`. With two
   clients writing to the same profile/log location, absence of lines cannot
   be reliably attributed to one process. Do not treat that observation as a
   per-client packet trace.

## Preserved evidence

- Strongest failed-run archive:
  `C:\intelprop\thorgor archive\ThorGor_SESSION_20260814_184837.zip`
- Extracted working copy:
  `C:\Users\Thor\Documents\Codex\2026-08-14\https-github-com-lightningfastcomputing-thorgor-hon\work\v72_crash_184837`
- Shared client console:
  `C:\Users\Thor\Documents\Heroes of Newerth\game\console.log`
- UDP log:
  `C:\intelprop\thorgor archive\dashboard_logs\udp.log`
- Admission and manager captures:
  `C:\intelprop\thorgor archive\work`
- Rejected v72/v73 prototype builders and reproducible binaries remain only in
  the Codex workspace `work` directory for forensic comparison. They are not
  active or installed.

## Best next investigation

Continue from stable v65 and make the next pass observational only:

1. Give each local HoN instance a separate user-data/log directory if the
   client supports it, so host and joiner console evidence is attributable.
2. Capture and compare the stable-v65 admission/picking packet sequences for
   host and joiner without rewriting packets.
3. Compare per-account login, product, inventory, upgrade, and game-client
   authorization payloads using account ID/cookie—not source IP alone.
4. Identify the first reliable command or entitlement transition present for
   the host and absent for the joiner.
5. Prefer a master-server/session correction or a narrowly scoped cgame-side
   initialization fix. Do not add another K2 periodic state-block sender.

## Normal restart

Use only:

`C:\intelprop\thorgor archive\1_START_V61_COMPLETE_REGISTRY_GUARD.bat`

Confirm its title says `v71 Stable K2` before testing.
