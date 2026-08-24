# ThorGor architecture

ThorGor is moving from milestone-numbered scripts to stable subsystem names.
The frozen v77 behavior remains available throughout the migration.

## Runtime flow

```text
client -> master/auth -> chat -> matchmaking or game creation
       -> game manager -> dedicated slave -> lobby/match -> frontend
```

## Package boundaries

- `thorgor.master`: accounts, SRP authentication, sessions, and the master HTTP service.
- `thorgor.chat`: protocol framing, channel state, and the chat TCP service.
- `thorgor.matchmaking`: queue policy, match formation, and connection assignments.
- `thorgor.game_manager`: dedicated-server registry and match lifecycle.
- `thorgor.protocols`: named master, chat, and game wire formats.
- `thorgor.patches`: patch identities, manifests, validation, and generation.
- `thorgor.tools`: packet evidence, account management, and the dashboard.

## Migration rule

Stable modules may temporarily delegate to a frozen implementation through
`thorgor.compat`. No new feature should import a version-numbered script
directly. Each adapter is removed only after protocol regression tests cover
the migrated behavior.

This creates a one-way migration: launchers stay operational, callers gain
stable imports immediately, and reverse-engineered behavior moves in small,
testable slices.

## State ownership

The existing shared JSON readiness file remains a compatibility transport.
The target owner is `game_manager.ServerRegistry`; the manager bridge will
publish typed state transitions there before the JSON file is retired.

