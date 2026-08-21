ThorGor v77 TAIL-RECIPIENT HERO STATE FIX

Finding from the v74 test
-------------------------
The joiner processed hero-list blocks 3 through 8, but each injected block
advanced its local state sequence. The server still sent snapshots at state
sequence 8 while the joiner expected 14, so the client dropped every snapshot
and remained visually in the lobby.

Why v75 and v76 were retired
----------------------------
Both builds replaced the stock periodic state-block section. The original
section queues the head client and then invokes a required game-state callback.
Removing that callback corrupted the first snapshot and produced
"13253 unread bits" after the loading bar completed. The v76 trace confirmed
that no added hero block had been sent before the failure.

v77 fix
-------
K2's original head-client queue and game-state callback remain byte-for-byte
unchanged. A small addendum runs only at the original loop tail. For the
packet-traced hero-list blocks 3 through 8, it queues stale copies for linked
clients after the head through K2's original guarded QueueStateBlock function.
The v74 UDP injection remains disabled.

Required hashes
---------------
K2 v65 input:
82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB

K2 v77 output:
25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026

cgame v61:
88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988

Install K2 v77 on every machine that runs HoN. Run the v77 stack launcher only
on the dev/server machine. Start the host first, then the joiner, and verify
portraits, hover names, selection, and the transition into gameplay.
