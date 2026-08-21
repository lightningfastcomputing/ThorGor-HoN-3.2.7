# v64 linked-client picking state — 2026-08-14

v64 fixes the remaining host-only hero roster during the picking phase.

The v63 linked-list walk correctly found both connected clients, and its
state-string path delivered both player names. Client logs then showed the
decisive difference at the picking transition: the host received state blocks
3 through 8 and loaded the hero icons, while the joined client received none
of those blocks.

The original block queue helper applies a client-number guard after checking
that the connection is active. That transient number can be `-1` for a joined
client during the local picking transition, so the helper silently discarded
the broadcast despite the client remaining in the active linked list.

v64 keeps the normal helper unchanged for admission and targeted sends. Only
the all-linked-client block broadcast uses a small wrapper that preserves the
active-connection check and enters after the transient client-number guard.
The v63 player-name delivery and v61 client registry guards remain unchanged.

Verified K2 v64 SHA-256:

`570BFB5A9AE90AAACDAEBEBCCA2BE0572DC631D7211AC889226A4DF7359CF043`
