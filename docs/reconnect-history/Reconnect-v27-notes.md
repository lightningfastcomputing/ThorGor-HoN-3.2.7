# Reconnect v27: active-match-only command ownership

V27 rejects the v26 lobby behavior while retaining its intended reconnect
command repair. The v26 live trace showed ordinary player2 correctly created
as account 3/client 1, but the shared player-map miss fallback was reachable in
the lobby and interfered with normal player lifecycle and slot selection.

V27 proves three conditions before scanning retained players: the queried map
is exactly the singleton CGame player map, a CGameInfo exists, and its phase is
5 or later. Lobby phase therefore returns the stock miss result without reading
any player value. Active gameplay can still resolve a reconnected CPlayer whose
live client field no longer matches its historical tree key.

Native x86 tests now explicitly execute both phases: client 2 must remain a
miss in lobby phase 1 and must resolve the retained player in gameplay phase 5.
Normal key hits remain stock and unrelated maps remain untouched.

Install with `INSTALL_RECONNECT_V27.bat` while all HoN clients are closed. First
verify player2 can join a lobby slot normally. Then start the match, reconnect
player2, and verify movement plus ability leveling.
