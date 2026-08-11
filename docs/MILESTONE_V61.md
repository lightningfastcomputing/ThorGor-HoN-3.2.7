# v61 best milestone — 2026-08-11

## Confirmed working

- Two PCs can authenticate against the LAN backend.
- LAN chat works.
- Either client can discover and join a hosted lobby.
- Lobby slots and player state synchronize.
- The server PC can host with the remote client joined.
- The countdown completes and both clients reach hero selection.
- A match hosted by the server PC can load Caldavar with the remote client connected.
- The tested remote core game files matched the server installation byte-for-byte.

## Interoperability patches

- K2 v57 fixes the newly admitted client callback and preserves the earlier manager/server interoperability work.
- cgame v61 guards finalization plus primary and fallback entity-registry lookup results during the match transition.

Expected generated SHA-256 values:

- `k2.dll`: `6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF`
- `cgame.dll`: `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`

No DLL is included in the repository. The patch builders require exact user-supplied HoN 3.2.7.1 source hashes.

## Known remaining defects

- When the server PC hosts, the remote client can reach hero selection but may display generic placeholder portraits instead of hero artwork.
- The remote client has crashed when creating or starting a match, while the server PC can create and start a solo match successfully.
- Core asset parity was verified, so the placeholder issue is not explained by missing `resources0.s2z`, `textures.s2z`, `game_shared.dll`, or the v61 `cgame.dll`.

## Next diagnostic

Swap the two player accounts between machines and observe whether placeholder portraits remain with the remote machine or follow the account. This separates local runtime state from backend account/hero-availability data.
