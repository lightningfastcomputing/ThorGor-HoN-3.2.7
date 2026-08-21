# v63 multi-client state delivery — 2026-08-14

## Symptom

The hosting player received player names and hero availability, while a player
joining the same created game saw an incomplete slot and placeholder hero
portraits. Reversing the two accounts left the defect with the joining client,
and the joining client's reliable admission stream was fully acknowledged.

## Root cause and fix

Two K2 dynamic-state paths queued state blocks and state strings only through
the linked-list head. v63 preserves the verified v57 admission behavior but
walks `CClientConnection::next` and queues each update for every linked client.
These dynamic records drive both lobby player data and hero availability.

Follow-up testing confirmed the state-delivery change fixed player names, while
the joining client still rendered placeholder hero portraits. The remaining
gate was account ownership: unlike the host path, the joining client consults
the login and game-auth `my_upgrades` collection while building its hero
registry. The private backend now advertises the client's built-in
`h.AllHeroes.Hero` product on both paths. This unlocks the locally installed
catalog; it does not distribute or modify game assets.

The cgame v61 registry guards remain unchanged. The v63 output is built only
from the exact verified v57 baseline and has SHA-256:

`9C3D512ACFF549ACBF82A0A46A59D64C6F0F06AD26C831F0DAB7F10A793ED885`

## Runtime verification

The source builder, byte-level hook checks, installer hash chain, and regression
tests are reproducible. Loading the new DLL requires closing all HoN player and
dedicated-server processes, installing the patch, and starting a fresh game.
The launchers honor an existing `HON_HOME` environment variable for development
installs while retaining the Program Files location as their default.
