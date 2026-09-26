# Reconnect v36 — creator-departure connection-registry fallback

V36 keeps the live-proven v32 joiner reconnect path and v35's safe
host-migration player-map fallback.

The September 26 v35 live test used the expected game.dll hash and showed:

- player2 disconnected and reconnected as the correct retained player;
- player2 had live client number 2 and remained in the native player map;
- creator departure caused a clean slave shutdown, not an access violation;
- the other client stopped receiving server packets immediately afterward.

After v35 resolves the retained `CPlayer`, host migration has three successor
guards. The live trace proves the player pointer exists and its live number is
not `-1`. The remaining rejected guard is `CHostServer::GetClient(2)`: K2's
connection registry can remain keyed by the historical allocation after a
successful reconnect.

V36 detours the guard block at game.dll RVA `0x32FE1`. A non-null K2 connection
returns to the untouched stock path. If only that lookup is null, v36 requires
the already-resolved player and a valid live number, marks that CPlayer as the
new game host, and resumes the stock host-ID assignment and `0xB2` broadcast at
RVA `0x33001`. It never dereferences the null connection. Missing players and
invalid live numbers retain stock rejection.

Verified outputs:

- game.dll: `BADCFCCA8A784FBD536FB0849EEA5B614BE41F344EDF9E176D8B498B69F58FA3`
- k2.dll: `BA14F2931FF6F5FB9377FAECECA2F3A96A53436D61CD7984D002A5F24616B35C`
- automated suite: 75 tests passed, including native execution of both the null
  fallback and untouched non-null path.

Install locally with `INSTALL_RECONNECT_V36.bat`, start a fresh match, verify
player2 reconnect first, then disconnect and reconnect the creator.
