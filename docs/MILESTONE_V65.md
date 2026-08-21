# v65 authoritative linked-client broadcasts — 2026-08-14

v65 addresses the remaining host-only hero roster during the picking phase.

The v64 retest proved that both network routes remained active while the joined
client still received none of state blocks 3 through 8. The host received all
six blocks and immediately loaded the hero portraits. This ruled out assets,
entitlements, routing, the linked-list traversal, and the transient client
number as the remaining cause.

The block queue helper had one additional readiness-field filter. That field
was stale for the joined client even while the client remained connected and
exchanged packets normally. v65 therefore treats membership in the server's
authoritative linked-client list as the recipient test for dynamic state-block
broadcasts.

The original queue helper and both of its readiness filters remain unchanged
for admission and targeted sends. Only the explicit all-linked-client broadcast
wrapper enters the original queue body after those filters. v63 player-name
delivery and the v61 client registry guards remain unchanged.

Verified K2 v65 SHA-256:

`82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB`
