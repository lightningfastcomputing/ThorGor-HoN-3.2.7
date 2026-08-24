# Joined-client picker repair — 2026-08-24

The stable v65 two-client capture identified the remaining portrait failure at
the wire level.  During the same picking transition, the match creator received
a complete 643-byte reliable packet containing state blocks 3 through 8.  The
joined client received the matching 18-byte packet prefix with every one of
those blocks absent.

ThorGor now enables the existing bounded UDP repair in the refactored dashboard.
It caches a suffix only after validating a complete creator packet containing
exactly blocks 3 through 8, and appends it only to the exact 18-byte truncated
joiner packet.  Packets with another prefix, a partial/different block set, or a
creator route are not changed.

This keeps the verified v65 K2 DLL installed and avoids the unsafe periodic K2
reconciliation and v77 tail-recipient paths.  Successful repairs are recorded
as `HERO_BLOCK_CACHE` and `JOINER_HERO_BLOCK_REPAIR` in the UDP service log.
