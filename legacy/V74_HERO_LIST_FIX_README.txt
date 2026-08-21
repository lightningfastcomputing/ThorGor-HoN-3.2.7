ThorGor v74 ONE-SHOT JOINED-CLIENT HERO-LIST FIX
================================================

The v73 capture proved that the host receives a reliable picking packet with
state blocks 3, 4, 5, 6, 7, and 8, while the joiner receives the identical
packet prefix with the entire 625-byte hero-list suffix omitted.

v74 validates and caches that exact six-block suffix from the host delivery.
When a non-host route receives the exact truncated 18-byte packet, v74 appends
the cached suffix once before forwarding it. No other packet shape is changed.

Safety guards
-------------
- Feature is opt-in and enabled only by the v74 dashboard launcher.
- Source must be the authenticated hosting route with a match key.
- Target must be an authenticated non-host route.
- Packet prefix and truncated length must match the v73 evidence exactly.
- Suffix must parse as exactly blocks 3 through 8.
- Every block must be non-empty and its payload divisible into five-byte hero records.
- No periodic injection, replay loop, new reliable sequence, or DLL change.

Test
----
1. Run START_V74_HERO_LIST_FIX.bat on the dev/server PC.
2. Use player as host and pwnrbwnr as joiner.
3. Start one match and inspect the joiner's hero grid.
4. Hover a hero, click it, and select a different hero than the host.
5. Close clients and then the dashboard normally.
