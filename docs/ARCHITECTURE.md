# ThorGor architecture

ThorGor HoN 3.2.7 LAN Sandbox is a self-contained Python package. Production
execution does not use a compatibility loader or a bundled legacy runtime.

## Runtime flow

```text
client -> master/auth -> chat -> server discovery
       -> manager -> logical slave -> sleeping dedicated child
       -> allocation -> wake/StartGame -> lobby/match
```

The stock manager/dedicated relationship is preserved. ThorGor does not replace
it with a direct dedicated-process shortcut.

## Package boundaries

- `thorgor.master`: accounts, SRP authentication, sessions, and HTTP service.
- `thorgor.chat`: chat framing, compatibility responses, channels, and TCP service.
- `thorgor.protocols`: master, chat, UDP discovery, routing, and game wire behavior.
- `thorgor.game_manager`: manager process, control bridge, native match ID,
  runtime state, registry, and lifecycle.
- `thorgor.matchmaking`: tested queue/assignment domain logic and explicit
  integration status.
- `thorgor.patches`: semantic manifests, frozen builders, verification, and install.
- `thorgor.tools`: dashboard, account manager, and packet evidence.

Dependencies point from tools to services and from services to domain/protocol
modules. Protocol modules do not own GUI or process orchestration.

## Runtime data

Mutable databases, logs, captures, and shared compatibility state live under
`thorgor/var` by default. Set `THORGOR_DATA_HOME` to relocate them. This folder
is generated and excluded from source control.

The shared readiness JSON remains a compatibility transport among independently
running processes. Consolidating its ownership is future work and must be done
as a separately tested behavior change.

## Supported launch path

`thorgor/START_STACK.bat` locates Python, verifies/installs named patches,
cleans stale stack processes, resets volatile state, and runs:

```powershell
python -m thorgor dashboard
```

Every service subprocess is launched with a stable `thorgor.*` module name.
