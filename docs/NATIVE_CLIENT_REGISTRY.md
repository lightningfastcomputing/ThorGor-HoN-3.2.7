# Managed client registry continuity

The creator-departure freeze is a native transport-registry loss. It is
independent of reconnect admission or retained CPlayer identity.

## Evidence from frozen v39

On 2026-11-04, auth, lobby authority, native admission, and active gameplay
passed. Two fresh default creator-departure regressions failed with
`reproduced_freeze`. A third instrumented v39 control observed the same freeze
for 15 seconds, using explicit expected-bug mode.

Before C3, both simulated clients receive about 20 fresh complete snapshots
per second. The native connection chain is:

```
CHostServer+180 -> creator connection 0 -> (+8430) joiner connection 1 -> null
```

Retail local-client removal at K2 RVA 2F2DD0 invokes the game removal callback,
destroys the head through 474F0 at 2F2E56, and clears CHostServer+180 at 2F2E5B.
Frozen v39 suppresses managed-server shutdown, preserving the process. However,
ThorGor's linked GetClient/input/send/state-queue wrappers all start at +180.
They lose access to every surviving connection when it becomes null.

Read-only live evidence recorded the joiner object still in state 4 with the
same account and client number after the head disappeared. Its receive time
and acknowledged frame stopped advancing. CPlayer identity and hero remained
present, native phase stayed 6, and engine time continued advancing.

The instrumented control established the exact delivery boundary:

- Newly generated native snapshots advanced from frame 2879 to 3161 after C3.
- The native registry head stayed null in all 15 observation windows.
- The joiner's proxy route kept forwarding about 20 packets per second to its
  unchanged upstream port, receiving zero back from the native socket.
- The client decoded zero fresh snapshots and reported zero decoder errors.
- Master reservation release and proxy retirement affected the creator route;
  the joiner route and native match ID remained present. The manager connection
  and owned slave survived. No new StartGame or process replacement was needed.

The failure therefore occurs before native transmission: snapshot generation
continues, but recipient enumeration has lost its root. Proxy rerouting,
snapshot fabrication, automatic joiner reconnect, or hiding creator C3 would
not repair this registry invariant.

Evidence is in `../../outputs/creator-freeze-session/`, especially
`v39-instrumented.json`, its credential-free event log, and
`registry-observer.jsonl`. Native process pointers are run-specific.

## Separate successor patch

`dedicated.managed_registry` consumes the exact frozen v39 K2 image. It detours
the six-byte head load at 2F2E4A into unused padding at 70D800. Only for
manager-owned slaves (+2D0), it saves and detaches the next connection before
freeing the departing head, then assigns that successor to +180. It returns
through the existing v39 lifecycle path. An empty list stays empty. Unmanaged
hosting follows the unchanged v39 instructions.

No player-map rekey, account rewrite, hero transfer, connection replacement,
host-authority change, snapshot injection, or reconnect shortcut is involved.
The original v39 builders, catalog entry, installer default, and binaries stay
unchanged. The native harness applies the successor only to its disposable
installation when `--native-variant registry-continuity` is selected.

| Artifact | SHA-256 |
| --- | --- |
| Frozen v39 K2 input | CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D |
| Registry-continuity K2 output | 98138B1086092558014B4808D3AA75B00BA87450EA3112171F68CC3DC99048C2 |
| Unchanged v39 game.dll | 0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B |

Instruction-emulation tests execute the actual hook and snapshot-dispatch
wrapper. They cover multiple survivors, last/empty head, unmanaged behavior,
stack balance, and poisoning freed memory before recipient enumeration.
Live verification requires fresh snapshots in every one of 15 post-departure
windows, an advancing native clock, and stable match, player, hero, connection,
and endpoint identities. Successful command responses cannot pass this gate.

See `AUTONOMOUS_PROGRESS.md` for current live results and remaining coverage.

## Verified repair result

Three fresh repaired matches passed on 2026-11-04. Each received 20-21 fresh
joiner snapshots in every one-second window for at least 15 seconds after
creator C3. The same native slave/server, match ID, CPlayer pointer, native
number, team, selected hero, spawned hero, transport object, and upstream
endpoint remained in use. Native receive/ACK counters advanced and every run
completed cleanup. Reports are registry-repair-1.json through
registry-repair-3.json under the evidence directory above.

The full repair suite ran 107 tests: 105 passed and two historical rejected
experiments skipped. This establishes snapshot continuity on protocol clients;
it does not establish rendering, movement, or reconnect recovery.
