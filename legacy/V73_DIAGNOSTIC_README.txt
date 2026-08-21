ThorGor v73 PER-ROUTE DIAGNOSTIC BUILD
======================================

Purpose
-------
Determine whether hero-list state reaches each authenticated client route
during the lobby-to-picking transition without relying on a shared console.log.

Safety
------
- No packet rewriting, injection, retransmission, or artificial delay.
- K2 v65, cgame v61, game_shared, master, chat, and manager behavior are unchanged.
- C9 keepalives are counted but omitted from the detailed JSONL to reduce noise.
- Evidence is checkpointed once per second so dashboard shutdown loses at most
  the final partial second of trace data.

Run
---
1. Run START_V73_DIAGNOSTIC.bat on the dev/server PC.
2. Use player as host and pwnrbwnr as joiner.
3. Prefer running the joiner on the laptop so its console.log is independent.
4. Create one lobby, join it, wait five seconds, and start the match.
5. At picking, wait ten seconds while the gray hero grid is visible.
6. Close the clients, then close the dashboard normally.

Evidence
--------
Per-route files are written to work\route_traces and included automatically in
the ThorGor_SESSION_*.zip created when the dashboard closes.

Each route produces:
- route_*.jsonl: complete reliable datagrams and compact control metadata
- route_*_summary.json: packet counts, reliable sequence coverage, gaps, ACKs,
  byte totals, truncation status, and first payload-byte distribution

Do not run extra lobby attempts during the same capture.
