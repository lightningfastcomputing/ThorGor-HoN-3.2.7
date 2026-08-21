ThorGor v75 SERVER-SIDE HERO STATE FIX

Finding from the v74 test
-------------------------
The joiner processed hero-list blocks 3 through 8, but each injected block
advanced its local state sequence. The server still sent snapshots at state
sequence 8 while the joiner expected 14, so the client dropped every snapshot
and remained visually in the lobby.

v75 fix
-------
K2 now reconciles only the packet-traced hero-list blocks 3 through 8 for each
linked client. It uses K2's original guarded QueueStateBlock function. That
function queues the data and advances the same client's server-side state
sequence together. The v74 UDP injection is disabled.

Required hashes
---------------
K2 v65 input:
82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB

K2 v75 output:
9D731944738C6CA014CB71F25F82DCE8634522247AB935513E2F5A0889C0BFF3

cgame v61:
88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988

Install K2 v75 on every machine that runs HoN. Run the v75 stack launcher only
on the dev/server machine. Start the host first, then the joiner, and verify
portraits, hover names, selection, and the transition into gameplay.
