# Milestone v71: joined-client product catalog

The 3.2.7.1 client requests `f=get_products` immediately after login. Earlier
ThorGor builds treated this as an unknown request and returned a generic
success object. The host could still populate its picker through the native
host path, while a joined client never completed its local product and hero
registry and displayed placeholder portraits.

v71 returns the legacy nine-section product-catalog envelope with a stable
CRC. Base hero ownership remains granted by the existing
`h.AllHeroes.Hero` account upgrade; base heroes are not individual store
products. Catalog requests are checked against the issued account cookie and
account ID.

Packet traces also confirm that the host and joiner use distinct UDP routes,
loopback identities, and host IDs, and that the joiner receives and
acknowledges the complete admission state stream. The colored/gray stars in
the lobby roster are self/roster indicators, not evidence that both players
are the match host. The authoritative match state contains only one host.

The stable v65 K2, v61 cgame, and v70 manager bridge remain unchanged.

Verification: 68 regression tests pass.

`ThorGorMasterServer.exe` SHA-256:

`B7A0C8F1A061EF8144D66A6E938AC62CF150AE4DFBCC90F81241B5485FD2EE43`
