# v69 all-heroes match option — 2026-08-14

v69 returns K2 to the stable v65 state-delivery build and fixes joined-player
hero availability in the normal match-creation protocol.

ThorGor already grants every LAN account the `h.AllHeroes.Hero` product, but
the native manager `0x26` start-game command omitted `allheroes:true`. The
reference Project KONGOR implementation includes that option in every bot and
matchmaking create-match command, and the match-server status protocol exposes
a corresponding all-heroes flag.

The manager bridge now removes any incoming `allheroes:` value and appends
exactly one `allheroes:true` before serializing the native start-game command.
This uses the stock match option rather than rewriting K2 state-block packets.

The v68 test produced `13301 unread bits` during initial state transfer and the
dedicated server disconnected shortly afterward. v66, v67, and v68 are retained
only as unsafe crash-forensics history and are not selected by launchers.

Compiled `ThorGorManagerBridge.exe` SHA-256:

`CDC7E0A6F4F0DE5002E2E76EE082B5C428E61F25A279942C542A447288BC1CD9`
