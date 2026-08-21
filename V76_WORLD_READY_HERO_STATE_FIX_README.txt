ThorGor v76 WORLD-READY HERO STATE FIX

Finding from the v74 test
-------------------------
The joiner processed hero-list blocks 3 through 8, but each injected block
advanced its local state sequence. The server still sent snapshots at state
sequence 8 while the joiner expected 14, so the client dropped every snapshot
and remained visually in the lobby.

Why v75 was retired
-------------------
v75 reconciled hero blocks while clients were still loading. The server then
encoded its first snapshot against an advanced state sequence before the
corresponding blocks were safely delivered. The client backed out with
"13253 unread bits" immediately after the loading bar completed.

v76 fix
-------
K2 now reconciles only the packet-traced hero-list blocks 3 through 8 for each
linked client, and only after that client reports that its world is fully
loaded. It uses K2's original guarded QueueStateBlock function. That function
queues the data and advances the same client's server-side state sequence
together. The v74 UDP injection remains disabled.

Required hashes
---------------
K2 v65 input:
82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB

K2 v76 output:
FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0

cgame v61:
88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988

Install K2 v76 on every machine that runs HoN. Run the v76 stack launcher only
on the dev/server machine. Start the host first, then the joiner, and verify
portraits, hover names, selection, and the transition into gameplay.
