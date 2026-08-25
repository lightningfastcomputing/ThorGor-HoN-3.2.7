# ThorGor HoN 3.2.7.1 Technical Handoff

**Session date:** 2026-08-24 through 2026-08-25  
**Repository:** `C:\intelprop\thorgor2`  
**Branch:** `refactored-architecture-2026-08-24`  
**HoN installation used for testing:** `C:\Program Files (x86)\Heroes of Newerth`

This document records the work completed during the session, the reasoning behind it, the current limits of the implementation, and a practical path for a developer or another LLM to continue safely.

## 1. Executive summary

The repository was cloned into `C:\intelprop\thorgor2` and exercised against HoN 3.2.7.1. The main work centered on joiner team chat, reliable UDP packet handling, UI presentation, and two distinct native crash signatures.

At the end of the session:

- The focused automated suite passes: **14 tests, 0 failures**.
- Installed K2 patch verification passes.
- Installed cgame patch verification passes.
- The reversible `resources999.s2z` UI overlay verifies.
- Host team chat was observed working normally.
- Joiner team chat now has team-aware routing, private delivery, retransmission deduplication, reliable-sequence translation, and UI normalization.
- After correcting the active-game chat callback argument forwarding, the user reported that lobby and active-game chat worked in a live retest. The complete multi-client matrix has not yet been repeated in full.
- The rejected native cgame chat experiment was removed. Do not restore it.
- A repeated cgame snapshot null dereference is now guarded.
- A second, older `game_shared.dll` object-corruption crash was identified but not patched.

No commits were created during this session. The working tree contains the changes described below.

## 2. Repository state at handoff

Current modified or new paths:

```text
M  patches/builders/complete_registry_guard.py
M  patches/catalog_data/dedicated.complete_registry_guard.json
M  patches/client/matchmaking_ui.py
M  patches/installer.py
M  protocols/game_protocol.py
?? tests/
```

`patches/installer.py` may appear modified because of line-ending or working-tree metadata even when its visible diff is empty. Check before committing rather than rewriting it unnecessarily.

Focused verification command:

```powershell
Set-Location 'C:\intelprop\thorgor2'
python -B -m unittest discover -s tests -v
```

Result at handoff:

```text
Ran 14 tests
OK
```

Patch installation/verification command used:

```powershell
Set-Location 'C:\intelprop\thorgor2'
python -B thorgor.py patches install --hon-home 'C:\Program Files (x86)\Heroes of Newerth'
```

Result at handoff:

```text
K2 v77 tail-recipient hero-state fix is already installed.
cgame registry guard is already installed.
ThorGor matchmaking UI overlay is already installed.
```

Writing beneath `Program Files (x86)` requires an elevated process. The earlier `PermissionError` on `resources999.s2z.thorgor.new` was an operating-system permission failure, not a patch-generation failure. Run the launcher or patch install from an Administrator PowerShell when installation is needed.

## 3. Architecture orientation

ThorGor is intentionally flattened at the repository root. `thorgor.py` exposes the checkout as the `thorgor` package so the stable `python -m thorgor` and absolute-import patterns continue to work even though the directory is named `thorgor2`.

The most relevant components are:

| Path | Responsibility |
| --- | --- |
| `thorgor.py` | Package shim for the flattened source tree. |
| `__main__.py` | Top-level CLI and service dispatch. |
| `game_manager/stack.py` | Canonical service startup plan used by the dashboard. |
| `master/` | Authentication and master-server behavior. |
| `chat/` | Account/chat backend services, separate from in-match UDP chat. |
| `game_manager/` | Dedicated server, manager process, runtime state, and process control. |
| `protocols/game_protocol.py` | Public-list UDP shim, route tracking, packet observation/repair, and current team-chat compatibility layer. |
| `patches/` | Reproducible binary/resource patch catalog, builders, installer, and verification. |
| `patches/client/matchmaking_ui.py` | Reversible `resources999.s2z` overlay builder and verifier. |
| `tests/` | Focused tests added for team chat and the cgame snapshot guard. |
| `var/dashboard_logs/` | Per-service logs displayed by the dashboard. |
| `var/work/hon_udp_shim_public_list.log` | Most useful detailed UDP route and packet-event log. |

The public-list preset is assembled in `game_manager/stack.py` and enables the relevant behavior in `protocols/game_protocol.py`. The UDP shim listens on port `11236`, authenticates C0 admission through the local master service, and maintains a separate upstream route for each HoN client.

## 4. Team-chat problem and implemented solution

### 4.1 Observed behavior

The stock/dedicated path behaved asymmetrically:

- The host/game creator could see team chat.
- Joiners sometimes could not see their own team messages.
- Joiners sometimes could not see teammate messages.
- Earlier attempts could leak the host's team chat to joiners on the opposite team.
- Native joiner team-chat events could arrive but fail to render because the joiner's sender/entity registry was incomplete.
- Pre-game lobby, picking, in-game, and spectator UI paths did not all format the compatibility message the same way.

The server's usable team-chat echo was effectively host-centric. A simple broadcast or conversion of every team event was therefore incorrect: it either lost joiner messages or crossed team boundaries.

### 4.2 Relevant packet shapes

The implementation currently recognizes exact HoN 3.2.7.1 packet forms:

```text
Reliable data header:       00 00 03 <sequence:u32-le>
Reliable ACK header:        00 00 05 <sequence:u32-le>
Client team chat payload:   C8 5C <message> 00 01
Client team selection:      C8 01 <team:u32-le> <slot:u32-le>
Server team chat payload:   5F 03 <sender:u8> <message> 00
Server all-chat payload:    5F 02 <sender:u8> <message> 00
```

Only teams `1` and `2` and slots `0` through `4` are accepted by the selection parser. Unknown team membership is fail-closed: the message is routed to nobody rather than broadcast.

### 4.3 Proxy-side routing

The current code in `protocols/game_protocol.py` adds:

- Exact parsing helpers for client team chat, client team selection, and server team chat.
- Per-route team state in `route_team`.
- Per-route player-number state in `route_player_number`.
- Recipient selection through `team_chat_recipient_routes()`.
- Deduplication of reliable client retransmissions through `remember_reliable_sequence()`.
- Pending chat correlation so a server echo can be associated with the route/name that originated it.
- Direct private delivery for joiners on the team opposite the host.
- Host-native team-echo mirroring only to joiners assigned to the originating team.
- Conversion of native joiner `5F 03` events to the UI-compatible private mirror form.

The compatibility message is carried as a private `5F 02` event containing this marker:

```text
[THORGOR_TEAM]
```

That marker allows the message to travel through the reliable generic-chat UI path without being mistaken for actual all chat after it reaches the patched UI.

### 4.4 Reliable sequence translation

Injecting a reliable packet between genuine server packets changes the sequence visible to one client. Sending an injected event without translating subsequent sequence numbers caused loss, retries, or inconsistent behavior.

The shim now maintains per-route state:

- `server_sequence_offset`
- `last_server_sequence`
- `server_sequence_translation`
- `server_ack_translation`

After a private injection, later genuine server packets have their reliable sequence shifted for that recipient. ACKs are translated back to the original server sequence. ACKs for shim-generated packets are consumed locally and are not forwarded upstream.

This is the most delicate part of the chat work. Any refactor must preserve these invariants:

1. A client must see one monotonic reliable sequence stream.
2. The dedicated server must see ACKs in its original sequence space.
3. A generated packet's ACK must never be sent to the dedicated server.
4. Retransmitted source chat packets must not generate duplicate visible messages.
5. Team membership must be known before private routing; unknown means no recipients.

### 4.5 UI normalization

`patches/client/matchmaking_ui.py` now patches four stock resources in the reversible overlay:

- `ui/scripts/chat.lua`
- `ui/scripts/game_new.lua`
- `ui/scripts/specui.lua`
- `ui/scripts/communicator.lua`

Each relevant boundary detects `[THORGOR_TEAM]`, removes it, changes the displayed `[ALL]` label to yellow `[TEAM]`, and sets the stock team-chat message type. The sender's native player color is retained. All chat remains blue `[ALL]`.

The four paths matter because HoN uses different UI entry points in the lobby, picking phase, active game, and spectator UI. Patching only `chat.lua` was not sufficient.

The active-game and spectator watch callbacks must preserve the leading watch-widget argument as well as the final `isMe`/`isSelf` flag. An earlier explicit callback signature omitted the widget, shifted every argument, and dropped the final flag. Lobby chat still worked through `communicator.lua`, but active-game delivery ended at `chat.lua` with `AtoB(nil)`. The corrected wrappers forward all seven arguments and are covered by `tests/test_team_chat_ui_overlay.py`.

Overlay installation was also made update-aware. If an older ThorGor-owned overlay exists but fails current verification, it is rebuilt and atomically replaced. A non-ThorGor `resources999.s2z` is not overwritten.

### 4.6 Known weaknesses still requiring work

The implementation passes focused automated tests and a live lobby/gameplay retest, but it should not yet be considered finished:

- The corrected lobby and active-game paths were reported working, but the full three-client, two-team matrix still needs a recorded repeat across lobby, picking, active game, and spectator UI.
- `pending_team_chat` correlates primarily by message bytes and team. Identical messages sent close together by multiple teammates may match ambiguously.
- A temporary player number is allocated before an authoritative server echo identifies the sender. This can be wrong in unusual join order/reconnect cases.
- Reliable translation dictionaries are cleared when a route closes but are not pruned during a very long route. They should be bounded by an ACK/window policy.
- Direct delivery for the team opposite the host exists because of the server asymmetry. This special case needs integration tests with real packet fixtures.
- The team-selection parser depends on the exact observed `C8 01` payload. Spectator/team changes, reconnects, or other lobby modes need explicit captures and tests.
- Most of the state currently lives as closure dictionaries inside a very large `main()` function, making correctness difficult to reason about.

## 5. Binary patch work

### 5.1 Stable cgame registry/snapshot guard

Several dumps showed the same native crash:

```text
cgame.dll RVA 0x1057C5
instruction: mov edx, [ebx]
condition:   snapshot entity factory returned null in EAX/EBX
```

Affected dumps observed during analysis:

```text
crash_3.2.7.1_0005.dmp
crash_3.2.7.1_0008.dmp
crash_3.2.7.1_0009.dmp
crash_3.2.7.1_0010.dmp
crash_3.2.7.1_0011.dmp
```

`patches/builders/complete_registry_guard.py` now adds a null guard at:

```text
Hook RVA:       0x1057C0
Code-cave RVA:  0x1A0280
Null skip RVA:  0x106236
```

For a non-null factory result, the overwritten instructions execute and control returns normally. For null, the hook return address is discarded and execution resumes through the function's existing next-snapshot path.

Verified stock cgame SHA-256:

```text
45B3CE39214EFD82D12DA8B01E73494CEE983D6DB4891C7D95DF10B2EAA70B02
```

Expected stable output SHA-256:

```text
E4298CF1842D2F3C5C9C86C6AEA450D618B4CE6393BCAAD9008314AE78103DA7
```

The patch catalog entry is now revision `v79` and records the dump evidence.

### 5.2 Rejected native chat experiment

A native cgame team-chat experiment was tested and then rejected after all three HoN instances exited around the `5, 4, 3, 2, 1` game transition. The installer recognizes its hash so it can restore the stable registry-guard build:

```text
Rejected output SHA-256:
1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF
```

Do not reintroduce this native chat patch. Team chat currently belongs in the UDP compatibility layer plus reversible Lua overlay, where it can be observed, tested, and rolled back more safely.

### 5.3 Separate recurring game_shared crash

The final joiner lobby-connect crash dump, `crash_3.2.7.1_0012.dmp`, was analyzed. It is **not** the guarded `cgame.dll + 0x1057C5` failure and did not occur in the team-chat code.

The exception jumped to invalid address `0x0000053F`. The immediate caller was:

```text
game_shared.dll RVA 0x232E8A: call edx
```

The object at `EDI` had a corrupted/unusable virtual-table pointer `0x44932057`, causing the indirect call target to become `0x53F`. Dump `0006` contains the same call site, same bad virtual-table value, and a bad target of `0x500`. Therefore this crash predates the latest chat work and is a recurring object-corruption/use-after-free class of failure, not a new chat regression.

The UDP log showed no team-chat event near the crash. The joiner connected at approximately `00:14:24`, received a roughly 3.3 KiB server state burst near `00:14:38`, and crashed at `00:14:39`.

Do not casually patch out the indirect call. The surrounding logic iterates game objects and expects a valid polymorphic object. A safe fix requires identifying object lifetime/type ownership or adding a carefully validated pointer guard with a known correct skip path. Work on this crash separately from chat so failures remain attributable.

## 6. Recommended refactor plan

The current branch is called a refactored architecture, but `protocols/game_protocol.py` still concentrates too much protocol state and behavior in one function. The next refactor should preserve behavior first and change structure second.

### Phase 1: freeze and document the baseline

1. Review the current diff file by file.
2. Normalize only intentional line endings; do not mechanically rewrite binary-anchor files.
3. Run the 11 focused tests.
4. Verify installed patches.
5. Perform the manual test matrix in section 8.
6. Commit the cgame crash guard separately from the chat compatibility layer if possible.

Suggested commit separation:

```text
1. guard nullable cgame snapshot entity creation
2. add team-aware joiner chat relay and reliable translation
3. normalize mirrored team chat across HoN UI phases
4. add focused regression tests and handoff documentation
```

### Phase 2: extract packet codecs

Create a small module such as `protocols/game_packets.py` containing typed parsing/building functions. Use dataclasses for decoded events rather than returning loosely structured tuples.

Suggested types:

```text
ReliablePacket
ReliableAck
ClientTeamSelection
ClientTeamChat
ServerTeamChat
```

Each decoder should:

- Accept `bytes`.
- Validate the complete packet shape.
- Return `None` for non-matches.
- Avoid changing state.
- Have exact captured fixtures and malformed-input tests.

### Phase 3: extract reliable-stream translation

Move the sequence logic into a class such as `ReliableSequenceTranslator` with methods conceptually like:

```text
observe_server_packet(original_sequence) -> visible_sequence
allocate_injected_sequence() -> visible_sequence
translate_client_ack(visible_sequence) -> original_sequence | consume
prune(acknowledged_sequence or time/window)
```

Test wraparound at `0xFFFFFFFF`, duplicate server packets, out-of-order packets, injection before any server sequence, reconnect/reset, and ACKs for unknown sequences.

### Phase 4: extract team-chat relay state

Create a `TeamChatRelay` that owns:

- Route identity and authoritative player number.
- Team and slot membership.
- Pending source messages.
- Retransmission deduplication.
- Recipient calculation.
- Per-route reliable translators.

The UDP socket loop should ask this component for zero or more delivery actions rather than directly manipulating eight dictionaries.

Use explicit action objects such as:

```text
ForwardUpstream(packet)
ForwardToClient(route, packet)
ConsumeClientPacket(reason)
LogEvent(fields)
```

This makes the behavior deterministic and integration-testable without opening sockets.

### Phase 5: improve correlation and identity

Replace message-text correlation with a stronger key where protocol evidence permits it. Candidate inputs include client reliable sequence, route, timestamp/window, team, sender identity, and the corresponding server event order.

Do not assume connection order equals HoN player number. Prefer an authoritative roster/player mapping parsed from server state. Until that mapping is available, clearly mark temporary identities and never use them for authorization decisions.

### Phase 6: centralize UI marker handling

The same Lua normalization snippet is injected at four boundaries. Keep the four hooks, but generate their shared snippet from one Python helper so label/color behavior cannot drift.

Add overlay tests that:

- Build the archive deterministically.
- Verify all four entries contain the normalization.
- Assert `[THORGOR_TEAM]` is removed.
- Assert `[TEAM]` is yellow and `[ALL]` remains blue.
- Assert a ThorGor-owned older overlay updates.
- Assert an unowned `resources999.s2z` is never overwritten.

### Phase 7: investigate native crashes independently

Maintain a crash-signature table with dump name, module, RVA, exception type, registers, and likely cause. Never combine an unproven binary guard with protocol/chat changes in the same test build.

For the `game_shared.dll + 0x232E8A` crash:

1. Reproduce with stock UI/no chat activity if possible.
2. Capture the state packet immediately before failure.
3. Compare object creation/destruction and registry events between host and joiner.
4. Identify the concrete object type expected at `EDI`.
5. Determine whether the bad pointer comes from stale lifetime, malformed snapshot state, or an earlier overwrite.
6. Only then design a guard and validate its semantic skip path.

## 7. Guidance for another LLM

An LLM continuing this work should begin with evidence, not a fresh rewrite.

### Required first steps

1. Read this document completely.
2. Read `README.md`.
3. Inspect `git status`, `git diff --stat`, and the full diffs of the five modified source/catalog files.
4. Read both test files completely.
5. Run the focused test suite before editing.
6. Inspect the latest UDP log around the exact reproduction timestamp.
7. Preserve all user changes and verified binary hashes.

### Rules for safe continuation

- Do not treat text or color fixes as proof that routing is correct.
- Do not broadcast team chat when team state is unknown.
- Do not inject a reliable packet without translating later sequences and ACKs.
- Do not reuse a native binary patch merely because it seemed to fix one symptom.
- Do not edit the installed game DLL directly as the source of truth. Update the reproducible builder and expected hash, then install from the verified stock backup.
- Do not overwrite a resource overlay unless its ThorGor ownership marker verifies.
- Keep chat/protocol changes separate from native crash experiments.
- Prefer captured-packet fixtures and deterministic state-machine tests over live trial-and-error.
- When a live test fails, record exact client roles, teams, slots, message order, timestamp, and which window is host/joiner.

### Useful diagnostic facts

```text
Installed cgame stable hash:
E4298CF1842D2F3C5C9C86C6AEA450D618B4CE6393BCAAD9008314AE78103DA7

Rejected native chat cgame hash:
1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF

Recurring guarded cgame fault:
cgame.dll RVA 0x1057C5

Separate recurring game-object fault:
game_shared.dll RVA 0x232E8A -> invalid indirect target 0x500/0x53F

Detailed UDP log:
C:\intelprop\thorgor2\var\work\hon_udp_shim_public_list.log
```

## 8. Manual validation matrix

Automated tests do not prove HoN UI behavior. Use named clients and write down results for every cell.

### Lobby/picking/in-game phases

Repeat the following in the pre-game lobby, picking phase, and active game:

| Case | Expected result |
| --- | --- |
| Host sends all chat | Every client sees blue `[ALL]`; sender/player color is native. |
| Joiner sends all chat | Every client sees blue `[ALL]`; sender sees own message once. |
| Host sends team chat with same-team joiner | Host and same-team joiner see yellow `[TEAM]`; opposite team sees nothing. |
| Host sends team chat with only opposite-team joiners | Only host team sees it; opposite joiners see nothing. |
| Joiner sends team chat on host team | Host and same-team joiners see it once; opposite team sees nothing. |
| Joiner sends team chat on team opposite host | Sender and same-team joiners see it once; host team sees nothing. |
| Two opposite-team joiners send identical text quickly | Each correct team delivery appears once with correct sender identity. |
| Client retransmits due to loss | No duplicate visible chat line. |
| Joiner changes team/slot | Subsequent team chat follows the new team only. |
| Joiner disconnects/reconnects | Old route state is cleared; new messages use the new route/identity. |

Also verify:

- `[THORGOR_TEAM]` never appears visibly.
- Team `[T]`/`[TEAM]` is yellow on every client.
- All-chat `[A]`/`[ALL]` remains blue.
- Player-name colors agree between host and joiners.
- No messages display as literal `[ALL] ... [THORGOR_TEAM]...`.
- Starting after `5, 4, 3, 2, 1` does not crash any instance.

When testing three local instances, distinguish them visibly and record:

```text
Host:    username, team, slot, UDP route
Joiner1: username, team, slot, UDP route
Joiner2: username, team, slot, UDP route
```

Correlate failures with `PLAYER_TEAM`, `JOINER_TEAM_CHAT_*`, route statistics, and reliable sequence values in the UDP log.

## 9. Operational notes

Start the normal stack with:

```powershell
Set-Location 'C:\intelprop\thorgor2'
$env:HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'
.\START_STACK.bat
```

Use Administrator PowerShell when the launcher must install or update files under `Program Files (x86)`. Once patches are verified, routine service development generally does not require rewriting the HoN installation.

The dashboard service plan starts master, chat, UDP shim, backend, manager, and native match-ID support with staggered delays. If behavior looks inconsistent, first confirm that an older ThorGor process is not still bound to a service port and that the dashboard logs all belong to the same launch.

Runtime logs and generated state under `var/` are diagnostic artifacts, not source. Do not commit large packet logs, dashboard logs, crash dumps, or patched game binaries.

## 10. Definition of done for the next session

The team-chat work can be called complete only when:

1. All focused unit tests pass.
2. An integration/state-machine suite covers host team, opposite joiner team, retransmission, ACK translation, sequence wrap, reconnect, and identical messages.
3. The complete manual matrix passes in lobby, picking, and game phases.
4. No team message crosses a team boundary.
5. Every sender sees their own team message exactly once.
6. Sender names, portraits, and colors render consistently on host and joiners.
7. All chat remains unchanged.
8. Three-client transition through `5, 4, 3, 2, 1` completes repeatedly without a new crash signature.
9. The current changes are split into reviewable commits with hashes and rollback behavior documented.

The most productive next action is to extract and test the reliable/team-chat state machine before adding more packet special cases. That will make the remaining live discrepancies much easier to isolate and will leave the project in a form that a computer-science student, experienced engineer, or another LLM can reason about without reconstructing this session from packet logs.
