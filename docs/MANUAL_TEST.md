# Manual repaired-build test

The default launcher still selects frozen v39. Set
`THORGOR_NATIVE_VARIANT=registry-continuity` in every shell that installs or
verifies patches to select the creator-departure repair. The dashboard inherits
this setting and verifies the repaired K2 hash. Unknown variant names fail.
Omitting the setting selects v39; an installation upgraded by this opt-in can
restore its verified `k2.dll.thorgor_v39_baseline` backup. Both versions are
preserved. The harness has its own explicit `--native-variant` option.

This checkout has a separate prepared installation at
`work\manual-test\Heroes of Newerth`. The original
`C:\intelprop\Heroes of Newerth` and frozen fixtures remain unchanged.
For another checkout, copy the complete game directory there first.

Close existing HoN and ThorGor processes. Open PowerShell as Administrator:

```powershell
Set-Location 'C:\Users\Thor\Documents\Codex\2026-11-03\do-x20\work\ThorGor-HoN-3.2.7'
$env:HON_HOME = (Resolve-Path '.\work\manual-test\Heroes of Newerth').Path
$env:THORGOR_NATIVE_VARIANT = 'registry-continuity'
& .\START_STACK.bat 127.0.0.1
```

Wait for the dashboard's startup checks, dedicated slave, and Public Server Ready
to turn green. In a second Administrator PowerShell:

```powershell
Set-Location 'C:\Users\Thor\Documents\Codex\2026-11-03\do-x20\work\ThorGor-HoN-3.2.7'
$env:HON_HOME = (Resolve-Path '.\work\manual-test\Heroes of Newerth').Path
$env:THORGOR_NATIVE_VARIANT = 'registry-continuity'
py -m thorgor accounts
# Create two different enabled accounts, then exit the account manager.
py -m thorgor remote-setup --hon-home "$env:HON_HOME" --server-ip 127.0.0.1
if ($LASTEXITCODE -ne 0) { throw 'Client setup failed' }
py -m thorgor remote-client --hon-home "$env:HON_HOME" --server-ip 127.0.0.1 --instances 2
```

Remote setup installs/verifies the selected patches and maps the legacy chat
hostname to this server in the Windows hosts file. Two client processes share
the retail user profile; profile isolation has not been verified. Use distinct
accounts. For another PC, use the dashboard's LAN IPv4 address instead of
127.0.0.1, launch the stack with that IPv4, and configure that client's game
installation on the other PC.

1. Log in separately in both clients. Have one create a public game through
   the dedicated-server flow; have the other join it through the server browser.
   A Practice/local-host game does not exercise this repair.
2. Put the players on opposing teams, select heroes, and start the match. Check
   both clients can move their heroes and see ongoing world changes.
3. Disconnect the creator from the match while leaving the joiner connected.
   For at least 30 seconds, move the joiner, watch creeps/world activity, and
   check that the match clock advances. Record whether commands take effect.
4. Optionally reconnect the creator and check control of the original hero.
   Record this separately from the continuous-joiner result.

The automated tests already prove native snapshot continuity. These manual
checks establish visual gameplay and input behavior, which are not yet claimed
by the simulated clients. Native match-completion automation remains opt-in in
the harness; restart the stack for independent manual matches.

Use **Create Debug ZIP** on the dashboard immediately after a failure. Local
logs are in `var\dashboard_logs`, including `health_check.log` with the selected
variant and K2 hash. The repaired K2 SHA-256 begins `98138B1086092558`.
Debug archives may contain private runtime details; review before sharing.

To stop, close both graphical clients and the dashboard, then run:

```powershell
py -m thorgor cleanup
```

Closing the dashboard alone does not stop its background services. Do not run
the unattended native harness while the manual stack or clients are running.
