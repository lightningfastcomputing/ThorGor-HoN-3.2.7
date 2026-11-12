# Manual repaired-build test

`START_STACK.bat` and `START_REMOTE_CLIENT.bat` default to the installed
HoN 3.2.7.1 folder under Program Files (x86) and apply the `selection-recovery`
patches. Set `HON_HOME` before launching if the game is installed elsewhere.
`START_SELECTION_RECOVERY.bat` remains available for testing with a separate
game copy under `work\manual-test\Heroes of Newerth`.

Close existing HoN clients and dashboards. Open PowerShell as Administrator
in the checkout root and run the repaired launcher.

```powershell
.\START_STACK.bat 127.0.0.1
```

Wait for **Native build: selection-recovery** and for the startup checks,
dedicated slave, and Public Server Ready to turn green. In a second
PowerShell in the same checkout, open both clients.

```powershell
.\START_REMOTE_CLIENT.bat 127.0.0.1 2
```

Accept the administrator prompt. The launcher verifies the installed repair,
maps the legacy chat hostname to this server, and opens two game windows. Use two
different accounts. Create them with `py -m thorgor accounts` if needed.
Two client processes share the retail user profile.
For a LAN test, run `START_STACK.bat` with automatic LAN detection or pass the
server's LAN IPv4 explicitly. On each client PC run `START_REMOTE_CLIENT.bat`
and enter the dashboard's LAN IPv4.

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

In a fresh match, disconnect the host during the hero-selection countdown
before either player picks. Watch the joiner's countdown for 15 seconds before
reconnecting the host. Have the host pick a specific hero, then disconnect
and reconnect the joiner and pick a hero there too. Confirm both heroes appear
in Caldavar when the match starts.

The automated tests already prove native snapshot continuity. These manual
checks establish visual gameplay and input behavior, which are not yet claimed
by the simulated clients. Native match-completion automation remains opt-in in
the harness; restart the stack for independent manual matches.

Use **Create Debug ZIP** on the dashboard immediately after a failure. Local
logs are in `var\dashboard_logs`, including `health_check.log` with the selected
variant and DLL hashes. The expected prefixes are `98138B1086092558` for K2
and `2B7C387F1884637B` for game.dll. The debug ZIP records the current
dashboard variant in `dashboard_status.json`.
Debug archives may contain private runtime details; review before sharing.

To stop, close both graphical clients and the dashboard, then run:

```powershell
py -m thorgor cleanup
```

Closing the dashboard alone does not stop its background services. Do not run
the unattended native harness while the manual stack or clients are running.
