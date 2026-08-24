# LAN matchmaking path

The first proof is deliberately small: when two distinct LAN accounts queue
for All Pick, ThorGor forms one match, reserves one idle dedicated server, and
returns the same connection assignment to both clients.

```text
join queue -> two players available? -> reserve idle server
           -> create match id -> start lobby -> send connection assignment
```

## Implemented domain core

- `MatchQueue` is thread-safe, FIFO, mode-aware, and rejects duplicate accounts.
- `Matchmaker` forms a fixed-size match and restores requests if allocation fails.
- `ServerRegistry` deterministically reserves an idle dedicated server.
- `MatchLifecycle` permits only explicit created/allocated/lobby/playing/complete transitions.

The core intentionally has no Elo, regions, parties, penalties, or ranked
season concepts. Those are policy layers, not prerequisites for LAN protocol
completion.

## Integration milestones

1. Map the client's queue request and response command IDs in chat captures.
2. Translate a queue command into `MatchRequest` and expose queue status.
3. Adapt the verified manager `START GAME` path as the allocator.
4. Return one `GameAssignment` to both clients and enter the existing C0 flow.
5. Prove two players can finish, release the server, return to chat, and repeat.
6. Increase the fixed player count from 2 to 4, 6, and 10.

