# LAN matchmaking status

## Implemented and tested

- Thread-safe FIFO queues with duplicate-account rejection and mode filtering.
- Fixed-size match formation with rollback after allocation failure.
- Dedicated-server registry and explicit match lifecycle domain objects.
- A stable `MatchmakingService` boundary for simulation and future adapters.

## Not integrated

Live HoN 3.2.7 client matchmaking is not currently implemented. Queue command
IDs, responses, and the client transition packets have not been verified, so
ThorGor does not invent them or advertise the domain simulation as a live
service. `MatchmakingService.status()` reports `not_reversed` explicitly, and
the dashboard repeats that status.

## First live target

After packet evidence establishes the client boundary:

```text
two LAN clients -> compatible All Pick queue -> one available slave
                -> one match assignment -> both clients enter the same lobby
```

The existing tested queue and allocation interfaces can support that proof.
The missing work is protocol discovery and connection-transition integration,
not MMR, regions, parties, seasons, or ranked policy.
