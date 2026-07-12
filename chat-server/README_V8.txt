ThorGor HoN LAN Chat Server v8
================================

FIXES
-----
1. Uses the same thorgor_accounts.db as Master Server v24.
2. Validates account_id, cookie, and auth_hash for each connection.
3. Uses each account's database nickname instead of hardcoded pwnrbwnr.
4. Uses one shared channel ID per channel, not a new ID per client.
5. Sends packet 0x05 to existing members when a second user joins.
6. Keeps separate socket/client state for simultaneous local or LAN clients.

DATABASE
--------
The server tries to find one nearby thorgor_accounts.db automatically.
If it finds none or more than one, set the exact path in START_CHAT_SERVER_V8.bat:

    set "THORGOR_ACCOUNT_DB=C:\IP\thorgor\v24\thorgor_accounts.db"

The startup banner prints the selected database. It MUST be the same database
used by the running master server.

EXPECTED TEST
-------------
1. Start Master Server v24.
2. Start this chat server.
3. Log in client 1 as thor and join Any.
4. Log in client 2 as otto and join Any.
5. Both clients should remain connected, see both names, and exchange messages.
