ThorGor v72 DIAGNOSTIC-ONLY BUILD
=================================

Purpose
-------
Capture the first host-vs-joiner divergence behind:
1. non-host gray/missing hero portraits at hero selection
2. non-host not completing the expected game/chat transition

This build DOES NOT modify K2 or cgame behavior.
Keep the known-good client patch lineage (K2 v65 / cgame v61).

IMPORTANT
---------
Do NOT launch ThorGorDashboard.exe for this diagnostic run.
That frozen dashboard launches the pre-existing compiled Master/Chat EXEs and
would bypass the modified Python diagnostics.

Instead launch:
    START_V72_DIAGNOSTIC.bat

Optionally pass the server LAN IP:
    START_V72_DIAGNOSTIC.bat 192.168.1.154

What was added
--------------
Master server:
- MASTER_TRACE on every client-facing request
- resolves cookie-bearing requests to username/account_id when possible
- records lifecycle and match_id with each request
- richer get_products capture: resolved account, supplied account id,
  category counts/sizes and CRC

Chat server:
- TRANSITION_PROBE for recurring commands 0x0D07, 0x000F and 0x0011
- correlates each packet with account/account_id, channel, lifecycle, match_id
- decodes the 0x000F endpoint string when present
- saves structured transition_probe capture JSON files
- sends NO guessed responses; behavior remains observational

Controlled test
---------------
Use player as HOST and pwnrbwnr as JOINER.

1. Start ThorGor with START_V72_DIAGNOSTIC.bat.
2. Login as player and create the lobby.
3. Login as pwnrbwnr on the second client.
4. Join the existing lobby.
5. Wait about 5 seconds in the lobby.
6. Start the game.
7. Reach hero selection.
8. Wait about 10 seconds while the gray/missing hero state is visible.
9. Close the dashboard normally so it creates ThorGor_SESSION_*.zip.
10. Upload that newest session ZIP back to ChatGPT.

Do not perform extra lobby attempts during this run. A single clean chronology is
more useful than multiple mixed attempts.
