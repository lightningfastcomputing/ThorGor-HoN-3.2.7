# LAN matchmaking status

## Implemented and tested

- Thread-safe FIFO queues with duplicate-account rejection and mode filtering.
- Fixed-size match formation with rollback after allocation failure.
- Dedicated-server registry and explicit match lifecycle domain objects.
- A stable `MatchmakingService` boundary for simulation and future adapters.

## Live client boundary

HoN 3.2.7 chat protocol 47 is connected to the queue and allocator. ThorGor
decodes group creation, readiness, and resource-loading messages; reports queue
state and match discovery; waits for the manager bridge to create the native
match; then sends the stock auto-match connection packet to every assigned LAN
client.

## First live target

The first live target is:

```text
two LAN clients -> compatible All Pick queue -> one available slave
                -> one match assignment -> both clients enter the same lobby
```

Co-op uses a one-human bot match. PvP initially forms a match from two compatible
solo players. Parties, rating policy, seasons, leaver enforcement, and regional
latency selection remain later policy layers rather than requirements for the
LAN proof.
