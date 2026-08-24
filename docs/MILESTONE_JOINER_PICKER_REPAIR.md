# Joined-client picker proxy experiment — REJECTED (2026-08-24)

The stable v65 two-client capture identified the remaining portrait failure at
the wire level.  During the same picking transition, the match creator received
a complete 643-byte reliable packet containing state blocks 3 through 8.  The
joined client received the matching 18-byte packet prefix with every one of
those blocks absent.

The bounded UDP repair was enabled for one live test. It cached a suffix only
after validating a complete creator packet containing exactly blocks 3 through
8, then appended it to the exact 18-byte truncated joiner packet.

The recipient loaded the portraits but did not accept the lobby-to-picking
transition. The server then repeatedly retransmitted later reliable state. This
proves that copying the creator's suffix does not preserve the recipient-specific
state-block serialization contract even when the visible block framing validates.

The dashboard no longer enables this option. The verified v65 K2 DLL remains
installed, and the unsafe periodic K2 reconciliation and v77 tail-recipient paths
remain disabled.
