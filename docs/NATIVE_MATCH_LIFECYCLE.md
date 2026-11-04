# Authoritative native match completion

The same-service repeated-match regression exposed stale backend ownership.
In repeat-matches-1.json the native slave reached phase 7 and cleared its
CGameInfo, but backend match_id remained 1. An authenticated next-match
creator request was accepted as an ordinary joiner. The control bridge had
observed only genuine 40 association and 21 wake frames, with synthetic Idle
status. No genuine completion frame released the backend match.

The new optional native completion observer is in
`game_manager/native_match_id.py --complete-matches`. It uses the existing
loaded-module hash checks and native match-ID inspection. It arms only after
seeing phase 7 for the desired native match. It subsequently requires the same
PID, CGame pointer, match ID, and authenticated server/manager session, followed
by a null native game context within 180 seconds. Active creator departure
cannot satisfy this sequence. Missing state or command success alone cannot
complete a match.

The observer sends `native_match_complete` to the local master. This endpoint
requires the current server session (or current manager session when no server
session exists) and exactly the active match ID. Completion clears that match's
owner, reservation, and reconnect rows, preserving other matches' reconnects
and match history. A retry after completion is idempotent; a stale completion
cannot release a newer active match. The normal stack does not enable the
observer automatically. Lifecycle harness scenarios register a session before
admission when needed and explicitly start the observer as an owned service.

The first observer attempt lacked a registered session and failed safely.
A registration probe exposed and corrected the test HTTP helper's collision
between its listener-port argument and the protocol's `port` field. These
failed reports remain available for diagnosis.

## Live verification

`../../outputs/creator-freeze-session/repeat-matches-4.json` passed two complete
matches on the same slave PID 29184 and the same backend/manager services:

| Evidence | Match 1 | Match 2 |
| --- | --- | --- |
| Backend/native match ID | 1 | 2 |
| Native phase 6 and two independent streams | Passed | Passed |
| Native ended phase 7 | Passed | Passed |
| Native context cleared | Passed | Passed |
| Authenticated backend ownership release | Passed | Passed |

Before match 2 selection, native phase was 1, both selected types were FFFF,
both hero indices were FFFFFFFF, and native engine time was 950 ms. The
subsequent match selected fresh heroes and delivered ongoing snapshots.
The observer recorded completion for each ID without errors. Cleanup reaped
all processes, removed runtime/profile data, and restored the bootstrap log.

This establishes unattended lifecycle and repeated-match state isolation on
the audited native build. It does not establish rendering, movement, ability
input, or compatibility with other native layouts.
