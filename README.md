# ThorGor HoN 3.2.7 Authentication and Chat Experiment

> **Deprecated research experiment:** This project targets the obsolete Heroes of Newerth 3.2.7 client solely as a protocol-learning, interoperability, and game-preservation experiment.

This repository contains independently written Python code for a small local/LAN authentication and chat-server experiment. It demonstrates selected login, account, session, channel, and chat behavior observed while studying the legacy client.

## What is included

- Python authentication/master-server experiment
- Python local/LAN chat-server experiment
- Windows batch launchers and account-management helper
- Technical notes describing the tested behavior

## One-command Windows setup and launch

Paste the following command into PowerShell from any folder:

```powershell
$dir="$HOME\ThorGor-HoN-3.2.7"; if(Test-Path "$dir\.git"){git -C $dir pull}else{git clone https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git $dir}; Start-Process -FilePath "cmd.exe" -ArgumentList "/c","`"$dir\manage_accounts_v24.bat`"" -WorkingDirectory $dir -Wait; Start-Process -FilePath "cmd.exe" -ArgumentList "/k","`"$dir\start_masterserver_v24.bat`"" -WorkingDirectory $dir; Start-Process -FilePath "cmd.exe" -ArgumentList "/k","`"$dir\chat-server\START_CHAT_SERVER_V8.bat`"" -WorkingDirectory "$dir\chat-server"
```

This command:

- clones the repository into `%USERPROFILE%\ThorGor-HoN-3.2.7`
- pulls the latest version when the repository already exists
- opens the account manager first
- waits until the account-manager window is closed
- starts the master server in a separate command window
- starts the chat server in another command window

### Requirements

- Windows
- Git installed and available from PowerShell
- Python installed and available on `PATH`

The account manager must be closed before the master and chat servers are launched.

## Basic use

1. Install a current Python 3 release.
2. Run `manage_accounts_v24.bat` to create local test accounts.
3. Run `start_masterserver_v24.bat`.
4. Run `chat-server/START_CHAT_SERVER_V8.bat` to test chat functionality.
5. Read the included notes before changing network or hosts-file settings.
6. HoN 3.2.7 installer can be found below:

https://www.moddb.com/games/heroes-of-newerth/downloads/hon-client-327


## Independence notice

Independent educational research and game-preservation documentation. Not affiliated with, endorsed by, or sponsored by the original developers, publishers, Project KONGOR, or HoN Reborn. Heroes of Newerth and related names and assets belong to their respective rights holders.
