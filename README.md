# ThorGor HoN 3.2.7 Authentication and Chat Experiment

> **Deprecated research experiment:** This project targets the obsolete Heroes of Newerth 3.2.7 client solely as a protocol-learning, interoperability, and game-preservation experiment.

This repository contains independently written Python code for a small local/LAN authentication and chat-server experiment. It demonstrates selected login, account, session, channel, and chat behavior observed while studying the legacy client.

## What is included

- Python authentication/master-server experiment
- Python local/LAN chat-server experiment
- Windows batch launchers and account-management helper
- Technical notes describing the tested behavior

## What is not included

- No Heroes of Newerth client or server binaries
- No game assets, maps, textures, audio, or other copyrighted game files
- No official source code
- No credentials, account database, packet captures, or runtime logs

## Status and limitations

This is experimental research code, not a production server. It is incomplete, insecure for internet-facing deployment, and intended only for controlled local/LAN testing. Expect bugs and missing features.

## Basic use

1. Install a current Python 3 release.
2. Run `manage_accounts_v24.bat` to create local test accounts.
3. Run `start_masterserver_v24.bat`.
4. Run `chat-server/START_CHAT_SERVER_V8.bat` to test chat functionality.
5. This only works if your hosts file has these entries: 
--------------------------------------------------------
127.0.0.1 masterserver.euw.heroesofnewerth.com
127.0.0.1 masterserver.sea.heroesofnewerth.com
127.0.0.1 masterserver.naeu.heroesofnewerth.com
127.0.0.1 client.sea.heroesofnewerth.com
127.0.0.1 client.naeu.heroesofnewerth.com
127.0.0.1 client.euw.heroesofnewerth.com
127.0.0.1 client.gs.heroesofnewerth.com
127.0.0.1 chatserver.heroesofnewerth.com
127.0.0.1 authserver.heroesofnewerth.com
127.0.0.1 s2.honpatchserver.com
127.0.0.1 masterserver.hon.s2games.com
--------------------------------------------------------
6. HoN 3.2.7 installer can be found below:

https://www.moddb.com/games/heroes-of-newerth/downloads/hon-client-327

## Independence notice

Independent educational research and game-preservation documentation. Not affiliated with, endorsed by, or sponsored by the original developers, publishers, Project KONGOR, or HoN Reborn. Heroes of Newerth and related names and assets belong to their respective rights holders.

