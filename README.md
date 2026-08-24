# ThorGor HoN 3.2.7 LAN Sandbox

ThorGor is an independently written, local/LAN authentication, chat, server-browser, and dedicated-server interoperability experiment for the obsolete Heroes of Newerth 3.2.7.1 client. The project is intended for protocol research, preservation, and private LAN testing.

The operational stack is self-contained under the `thorgor/` package. Master,
chat, UDP discovery/routing, manager bridges, native match ID synchronization,
dashboard, tools, and patch installation run from stable package modules. There
is no compatibility loader or live legacy runtime. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/MATCHMAKING.md`](docs/MATCHMAKING.md).

The supported patch set retains the verified historical cgame v61 and stable K2 v65
behavior, but those revisions are patch metadata rather than the application
identity. See [the frozen-build manifest](FROZEN_WORKING_BUILD_2026-08-21.txt)
and [patch catalog](docs/PATCH_CATALOG.md).

## No game files are included

This repository does not contain `hon.exe`, HoN DLLs, maps, textures, archives, crash dumps, or other game assets. You must provide your own legitimate HoN 3.2.7.1 installation.

The patch installers verify exact SHA-256 hashes, generate the interoperability patches locally from your files, preserve verified backups, and verify the generated results. They refuse unknown client versions.

## Requirements

- Windows
- Git on `PATH`
- A user-supplied HoN 3.2.7.1 installation at `C:\intelprop\Heroes of Newerth` or `C:\Program Files (x86)\Heroes of Newerth`
- Administrator approval for hosts-file, firewall, and Program Files changes

Python 3.10 or newer is required on the stack/host PC. PyInstaller is needed only when rebuilding the checked-in executables from source.

## One-command acquire, install, and run

After cloning the refactored branch, launch the stable package entrypoint:

```powershell
thorgor\START_STACK.bat
```

Set `HON_HOME` first to use an installation other than
`C:\intelprop\Heroes of Newerth`. The package installer advances a verified
stock K2 through the required baseline chain, verifies cgame, preserves
hash-checked backups, and rejects unknown inputs.

The repository supplies ThorGor source but no HoN binaries or assets. During
startup, the installer verifies the user-supplied 3.2.7.1 DLL hashes, generates
the supported patches locally, resets volatile state, and starts the dashboard.

## First run

1. Clone or download this repository.
2. Run `thorgor\START_STACK.bat` on the stack/host PC.
3. On another PC with its own HoN 3.2.7.1 installation, copy the `thorgor`
   folder and run `START_REMOTE_CLIENT.bat SERVER_LAN_IP` beside
   `START_STACK.bat`.
4. Use the milestone's disposable local test accounts: `pwnrbwnr / pwnrbwnr` and `player / player`.

The stable launcher verifies and installs the supported named patches, resets
volatile state, preserves the proven startup order, and opens the dashboard.
Run `python -m thorgor accounts` to manage local accounts.

## Main components

- `thorgor/master/` — local authentication, sessions, and server-list service
- `thorgor/chat/` — LAN chat service and framing
- `thorgor/protocols/` — master, chat, UDP discovery, and game protocol behavior
- `thorgor/game_manager/` — authentic manager/slave orchestration and lifecycle
- `thorgor/patches/` — named, hash-gated patch manifests/builders/installer
- `thorgor/tools/` — dashboard, accounts, and packet evidence
- `thorgor/matchmaking/` — tested domain core; live client protocol is explicitly incomplete
- `legacy/` and root milestone files — historical/reference material, not production execution
- `tests/` — characterization, parity, architecture, and patch regression tests

## Stable developer interface

The new package can be used directly from the repository without installation:

```powershell
python -m thorgor patches list
python -m thorgor dashboard
python -m unittest discover -s tests -v
```

New code should import from `thorgor.master`, `thorgor.chat`,
`thorgor.matchmaking`, `thorgor.game_manager`, `thorgor.protocols`, or
`thorgor.patches`. Numbered root scripts are reference evidence only.

## Security and privacy

Runtime databases, logs, packet captures, debug bundles, and crash dumps can contain passwords, session proofs, cookies, LAN addresses, usernames, or captured traffic. They are excluded by `.gitignore` and must be reviewed and redacted before sharing. The documented milestone logins are intentionally public, disposable LAN test credentials—not private user credentials. See [SECURITY.md](SECURITY.md).

## Project status

This is unfinished preservation research, not a production service. Run it only on networks and systems you control. Do not expose it directly to the public Internet.

## Independence

This project is not affiliated with, endorsed by, or sponsored by the original developers or publishers, Project KONGOR, or HoN Reborn. Heroes of Newerth and related names, marks, and assets belong to their respective owners. See [NOTICE.md](NOTICE.md).

Independently authored source is available under the [MIT License](LICENSE). That license does not apply to third-party game software or assets.
