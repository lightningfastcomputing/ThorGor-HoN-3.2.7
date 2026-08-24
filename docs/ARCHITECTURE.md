# ThorGor service architecture

The production package is `thorgor/`. Runtime data belongs under `thorgor/var`
and is deliberately excluded from service source ownership.

## Master boundary

- `master/auth.py` owns HoN password and SRP primitives.
- `master/sessions.py` owns unfinished authentication sessions and expiry.
- `master/accounts.py` owns SQLite accounts, game cookies, and match records.
- `master/products.py` owns the private LAN product catalog.
- `master/server_list.py` owns CREATE/JOIN publication policy.
- `master/game_authorization.py` owns dedicated-server client identity responses.
- `master/server.py` is the legacy HTTP adapter and compatibility surface.

## Game protocol boundary

- `protocols/transport.py` owns K2 transport framing and C0 localization.
- `protocols/packet_decoding.py` owns byte decoding and packet descriptions.
- `protocols/admission.py` owns master-backed player/lobby authorization.
- `protocols/routing.py` owns typed per-client UDP route state.
- `protocols/tracing.py` owns passive evidence and exact hero-state validation.
- `protocols/game_protocol.py` remains the executable bridge and stable import facade.

## Startup and matchmaking

`game_manager/stack.py` is the typed canonical startup plan. The dashboard only
renders and launches that plan. Matchmaking exposes authenticated
`matchmaking_join`, `matchmaking_poll`, and `matchmaking_leave` master operations.
Two queued All Pick accounts cause a persistent match record and atomically claim
the proven idle dedicated slave. Native HoN queue command IDs and the frontend
transition packet remain reverse-engineering work; the endpoint does not claim
those unverified wire contracts.

## Patch catalog

`thorgor/patches/catalog_data` is the sole production manifest catalog. The old
version-suffixed root catalog was removed after preservation in Git and in the
v77 frozen build. Historical standalone patch scripts remain outside the package
only where old PowerShell/remote-host launchers still call them.
