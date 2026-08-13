# ThorGor HoN 3.2.7.1 LAN interoperability experiment

ThorGor is an independently written, local/LAN authentication, chat, server-browser, and dedicated-server interoperability experiment for the obsolete Heroes of Newerth 3.2.7.1 client. The project is intended for protocol research, preservation, and private LAN testing.

The current source milestone is **v61**. Two clients can authenticate, chat, discover and join a lobby, synchronize slots, enter hero selection, and—in the best tested direction—load Caldavar together. Important bugs remain; see [the milestone report](docs/MILESTONE_V61.md).

## No game files are included

This repository does not contain `hon.exe`, HoN DLLs, maps, textures, archives, crash dumps, or other game assets. You must provide your own legitimate HoN 3.2.7.1 installation.

The patch installers verify exact SHA-256 hashes, generate the interoperability patches locally from your files, preserve verified backups, and verify the generated results. They refuse unknown client versions.

## Requirements

- Windows
- Git on `PATH`
- A user-supplied HoN 3.2.7.1 installation at `C:\Program Files (x86)\Heroes of Newerth`
- Administrator approval for hosts-file, firewall, and Program Files changes

Python is not required to run the checked-in compiled distribution. Python 3.10 or newer and PyInstaller are needed only when rebuilding the executables from source.

## One-command acquire, install, and run

After the requirements above are installed, paste this single line into PowerShell. It clones the project into `%USERPROFILE%\ThorGor-HoN-3.2.7`, fast-forwards an existing clone, then launches the v61 installer and LAN stack with the required administrator prompt:

```powershell
$dir=Join-Path $env:USERPROFILE 'ThorGor-HoN-3.2.7'; if(Test-Path (Join-Path $dir '.git')){if(git -C $dir status --porcelain){throw "Existing ThorGor clone has local changes: $dir"}; git -C $dir fetch origin main; if($LASTEXITCODE -ne 0){throw 'Git fetch failed'}; git -C $dir show-ref --verify --quiet refs/heads/main; if($LASTEXITCODE -eq 0){git -C $dir switch main}else{git -C $dir switch --track -c main origin/main}; if($LASTEXITCODE -ne 0){throw 'Could not switch the existing clone to main'}; git -C $dir pull --ff-only origin main}else{git clone --branch main --single-branch https://github.com/lightningfastcomputing/ThorGor-HoN-3.2.7.git $dir}; if($LASTEXITCODE -ne 0){throw 'Git acquire/update failed'}; $launcher=Join-Path $dir '1_START_V61_COMPLETE_REGISTRY_GUARD.bat'; Start-Process -FilePath $launcher -Verb RunAs -WorkingDirectory $dir
```

The repository supplies independently built ThorGor executables, but no HoN binaries or assets. During startup, the installers verify the user-supplied 3.2.7.1 DLL hashes, generate the v57/v61 interoperability patches locally, preserve verified backups, configure the LAN firewall rules, provision the disposable test accounts, and start the compiled dashboard.

## First run

1. Clone or download this repository.
2. Run `1_START_V61_COMPLETE_REGISTRY_GUARD.bat` on the server PC. `START_LAN_STACK.bat` is an alias for the same launcher.
3. On another PC with its own HoN 3.2.7.1 installation, run `remote-client\START_REMOTE_PLAYER.bat SERVER_LAN_IP` from a complete copy of this repository.
4. Use the milestone's disposable local test accounts: `pwnrbwnr / pwnrbwnr` and `player / player`.

The launcher preserves the proven v61 startup order and automatically provisions the two disposable test accounts. `MANAGE_ACCOUNTS.bat` remains available for adding unique accounts.

## Main components

- `thorgor_hon_sandboxed_masterserver_v39.py` — local authentication and server-list experiment
- `chat-server/thorgor_hon_chatserver_v13.py` — LAN chat experiment
- `hon_udp_shim.py` — multi-client UDP routing and browser bridge
- `hon_manager_status_bridge_v42.py` — manager/slave status bridge
- `hon_native_matchid_bridge_v47.py` — native match-ID bridge
- `hon_v49_dashboard.py` — local stack dashboard
- `ThorGor*.exe` — PyInstaller one-file launchers for running without Python
- `BUILD_COMPILED.ps1` — reproducible local build recipe for the launchers
- `patches/` — source-only, hash-gated binary patch generators
- `REMOTE HOST/` — self-contained copy of the v57/v61 DLL patch installers and builders
- `tests/` — protocol and patch-manifest regression tests

## Security and privacy

Runtime databases, logs, packet captures, debug bundles, and crash dumps can contain passwords, session proofs, cookies, LAN addresses, usernames, or captured traffic. They are excluded by `.gitignore` and must be reviewed and redacted before sharing. The documented milestone logins are intentionally public, disposable LAN test credentials—not private user credentials. See [SECURITY.md](SECURITY.md).

## Project status

This is unfinished preservation research, not a production service. Run it only on networks and systems you control. Do not expose it directly to the public Internet.

## Independence

This project is not affiliated with, endorsed by, or sponsored by the original developers or publishers, Project KONGOR, or HoN Reborn. Heroes of Newerth and related names, marks, and assets belong to their respective owners. See [NOTICE.md](NOTICE.md).

Independently authored source is available under the [MIT License](LICENSE). That license does not apply to third-party game software or assets.
