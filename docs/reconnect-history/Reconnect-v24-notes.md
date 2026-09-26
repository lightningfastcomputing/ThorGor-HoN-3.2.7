# Reconnect v24: repair player identity on the working v23 flow

V24 keeps the complete v23 reconnect transport and game-layer flow intact.
It changes only how K2 preserves the authenticated account during admission.

The v23 live trace proved the failure mechanism:

- the gateway sent host account 2 and player2 account 3 correctly;
- both native CPlayers were stored as account 1;
- reconnect selected the first matching map entry, the host;
- player2's fresh native transport number 2 was therefore assigned to the host
  CPlayer, displacing the host without giving player2 valid hero ownership.

K2 had reused the old stack local before the authority hook read it. V24 saves
the parsed account earlier, then reads that saved value at the existing hook.
It does not change reconnect routing, connection tokens, allocation, transport
lookup, player-map iteration, or the v23 game.dll reconnect patch.

Expected native identities before reconnect are host account 2/client 0 and
player2 account 3/client 1. On reconnect, player2's retained CPlayer should be
selected by account 3 and adopt the fresh transport number without modifying
the host CPlayer.

Install with `INSTALL_RECONNECT_V24.bat` while all HoN clients are closed.

## Live milestone verification

Verified on 2026-09-18 with a two-client match:

- player2 disconnected, logged back in, and reconnected to the running match;
- player2 was rebound to the correct retained player rather than the host;
- the host remained connected and was not displaced;
- the dedicated slave remained running throughout reconnect;
- the reconnecting client loaded the match successfully.

Known remaining defect: the reconnected player2 client cannot yet issue working
hero-control commands. This milestone freezes the correct transport and player
identity behavior. Future work must preserve it and address only post-reconnect
hero ownership/input authorization.
