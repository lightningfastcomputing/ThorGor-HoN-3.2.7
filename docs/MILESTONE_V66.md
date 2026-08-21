# v66 per-client state reconciliation — REVERTED (unsafe)

v66 fixes a second first-client-only path in dynamic state-block delivery.

The immediate state-block hook already updated the first client's revision.
The server's periodic reconciliation then compared each host block only with
that first client. Once the first client matched, it skipped the queue call and
never examined later clients, allowing the joined player's hero roster to stay
permanently stale.

v66 replaces that head-only comparison with a loop over every non-disconnected
client in the server's authoritative linked list. For each state block it
compares the host revision with that individual client's revision and queues
only stale clients. This avoids unnecessary retransmission while allowing the
normal snapshot builder to carry blocks 3 through 8 to joined players.

Verified K2 v66 SHA-256:

`2BC131F1C40D9F84CAD288426B14B0DB1EE58E43FC64DB86FF5AEFFC82D58657`
