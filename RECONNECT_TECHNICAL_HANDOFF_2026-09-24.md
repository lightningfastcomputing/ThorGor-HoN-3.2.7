# ThorGor HoN 3.2.7 Reconnect — Technical Handoff

**Document date:** 2026-09-24  
**Target game:** Heroes of Newerth 3.2.7.1, Windows x86  
**Repository:** `lightningfastcomputing/ThorGor-HoN-3.2.7`  
**Branch:** `refactored-architecture-reconnect-wip`  
**Repository HEAD:** `4e9c9c0901bb1e5a0abead83b782ababecc10183` (`Resolve reconnect client snapshots by live identity`)  
**Active source checkout:** `C:\Users\Thor\Documents\Codex\2026-09-17\we\ThorGor-HoN-3.2.7`  
**Runnable package:** `C:\Users\Thor\Documents\Codex\2026-09-17\we\outputs\ThorGor-HoN-3.2.7`

This is the authoritative handoff for continuing reconnect development. Read it before changing the proxy, K2 patch, or game.dll patch. The most important lesson from this work is that reconnect is not one operation: transport admission, persistent account identity, retained player selection, hero ownership, connected-state restoration, real-time input dispatch, snapshot processing, and host migration are separate stages. Fixes that conflate those stages have repeatedly caused lobby regressions, displaced the host, or crashed the dedicated slave.

### 2026-09-26 update

V39 is now a frozen live milestone. Both creator and joiner reconnect to their
correct heroes with working controls, and neither departure kills the slave.
Joiner departure leaves the creator unaffected. Creator departure still freezes
the joiner's existing state stream; the joiner can clear that freeze by
disconnecting and reconnecting. Continue only from this narrow remaining state-
subscription defect. Local tag:
`reconnect-v39-both-accounts-reconnect-milestone`.

### Earlier v39 candidate

The v38 live test confirmed correct reconnect for both accounts and no slave
termination. It also showed player2 receiving zero server packets immediately
after creator departure despite continuing to send at 30 packets/second.
Creator reconnect restored server output only to the creator. The active local
candidate is **v39**: v38 K2 lifecycle retention plus the isolated v35
host-successor map-miss repair. V36 and v37 remain rejected. Expected game.dll:
`0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B`.

### Earlier v38 diagnosis

V37 live testing disproved the game-side retention diagnosis. The creator's
game removal callback completed, then the slave exited about 120 ms later.
Ghidra located the independent termination in K2's local-client cleanup: after
removing the special creator connection at `CHostServer+0x180`, K2 queues the
literal console command `StopServer`. The active local candidate is **v38**.
It restores live-proven v32 game.dll and bypasses only that command when
`CHostServer+0x2d0` marks a server-manager-owned dedicated slave. Local hosting
keeps retail shutdown behavior. V38 K2 hash:
`CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D`.
The 77-test suite passes with three rejected-build checks intentionally skipped;
live creator-departure/reconnect validation remains.

### Earlier 2026-09-26 investigation

V35 was live-tested with its expected `0DA7FA...` game.dll. It preserved the
working player2 reconnect but creator departure still caused a clean native
shutdown. The trace proved player2 remained a valid retained CPlayer with live
number 2. Because v35 supplies that player on the map miss and the number is not
`-1`, the remaining rejecting successor guard is K2
`CHostServer::GetClient(2)`, whose registry still uses historical allocation
identity. The current local candidate is **v36**. It bypasses only that null
lookup, never dereferences it, and resumes stock game-side host assignment.
V36 game.dll hash: `BADCFCCA8A784FBD536FB0849EEA5B614BE41F344EDF9E176D8B498B69F58FA3`.
All 75 automated tests pass. Live validation is still required.

---

## 1. Executive status

### What is proven to work

The committed and pushed **v32 milestone** is the last fully live-confirmed reconnect baseline.

In a two-client live match, v32 successfully did all of the following for ordinary player2:

1. Preserved the running match after player2 disconnected.
2. Presented the stock reconnect dialog after player2 logged back in.
3. Routed player2 back to the correct slave.
4. Reassociated player2 with the correct retained `CPlayer` and hero.
5. Kept the creator/host connected instead of replacing or defeating that player.
6. Loaded the map and state.
7. Restored movement and ability input without the earlier five-second delay.
8. Eliminated the repeated native error:

   `CGameServer::ProcessClientSnapshot() - Received snapshot with invalid client number 2`

The user described the final v32 live test as working perfectly. That milestone was pushed to `refactored-architecture-reconnect-wip` at commit `4e9c9c0`.

### What remains broken

On v32, when the original game creator (`player`, native client zero in the normal two-client test) disconnects, the native slave exits. Ordinary player2 can leave and reconnect successfully; creator departure is the special failure.

The current uncommitted working tree contains **v36**, a narrow continuation of
v35 intended to fix the final host-successor connection-registry rejection.

### Trust boundary

| Build | Trust level | Result |
|---|---|---|
| v32 | **Live-proven and pushed** | player2 reconnects correctly with immediate control; creator departure still kills the slave |
| v33 | Live-rejected | changing creator authority flags did not fix creator departure |
| v34 | **Live-rejected and dangerous** | corrupted an ordinary-disconnect branch target; player2 disconnect crashed the slave before reconnect |
| v35 | Live-rejected, diagnostically useful | safe player-map fallback, but creator departure still cleanly shut down the slave |
| v36 | Native-tested candidate, **not live-confirmed** | accepts v35's retained player when only K2 `GetClient(fresh_number)` is null |

Do not describe v36 as fixed until it passes the live acceptance sequence in section 14.

---

## 2. Preserve these recovery points

### Git milestones

| Milestone | Commit/tag | Meaning |
|---|---|---|
| Stable reconnect flow | `reconnect-v14-flow-milestone` / `d08da3a` | Reached the match without a slave crash, but returned as the wrong player |
| Correct player identity | `reconnect-v24-correct-player-milestone` / `eed140f` | Correct player and hero; no control |
| Correct player, no control | `reconnect-v28-correct-player-no-control-milestone` / `8b2cce1` | Correct retained player/entity ownership, still no gameplay input |
| Control restored, latency WIP | `reconnect-v29-control-restored-latency-wip` / `127b953` | Correct player and controls, but severe state latency |
| Connected-state repair | `f7f9477` | Corrected native connection flags/deadline; exposed snapshot lookup defect |
| Complete player2 reconnect | `4e9c9c0` | v32 live-proven baseline and current branch HEAD |

If a new experiment breaks ordinary player2 reconnect, return to `4e9c9c0` rather than reconstructing the path from memory.

### Binary hashes

| Artifact | SHA-256 | Meaning |
|---|---|---|
| Stock `game.dll` | `D345F8537ED9FD5C6705F8F1A9FA6663C5F4AE4476CD328B2D8F1074C044CF99` | Retail 3.2.7.1 input |
| Capacity-patched `game.dll` | `929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B` | Input to reconnect game patch |
| v32 `game.dll` | `D103A500E0ADA6E10F9F15EF8E22C4E5582AD8F7BE50FF109ABDC8E5F9ABBB30` | Last live-proven complete player2 reconnect |
| v34 `game.dll` | `4D15EABC17771907B6811DD6B401AC70A40199F1F7397BC038E2E91E8DD7ADC1` | Rejected; overwrites an independent branch target |
| v35 `game.dll` | `0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B` | Current uncommitted creator-departure candidate |
| v36 `game.dll` | `BADCFCCA8A784FBD536FB0849EEA5B614BE41F344EDF9E176D8B498B69F58FA3` | Current uncommitted connection-registry fallback candidate |
| K2 source | `25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026` | Input to creator/account authority patch |
| Proven K2 | `BA14F2931FF6F5FB9377FAECECA2F3A96A53436D61CD7984D002A5F24616B35C` | v32 and v35 expected K2 output |
| v33 K2 | `CC9662D54DD97AC6A7FEC514679061F333B04F5EF1C74AEE7FCEE63C121DA0B2` | Rejected authority experiment |

Hash every installed binary before interpreting a live test. A stale DLL makes the entire result ambiguous.

---

## 3. Current working-tree state

At the time of this handoff, the branch is clean relative to its remote at commit `4e9c9c0`, except for the local v35 candidate and its documentation.

Expected local changes:

- `README.md`
- `docs/LOBBY_AUTHORITY.md`
- `docs/RECONNECT.md`
- `game_manager/native_match_id.py`
- `patches/catalog_data/dedicated.reconnect_client_identity.json`
- `tests/test_native_lobby_authority.py`
- `INSTALL_RECONNECT_V35.bat` (untracked)
- `Reconnect-v35-notes.md` (untracked)
- `tools/install_reconnect_v35.ps1` (untracked)

`patches/builders/creator_authority.py` may appear modified because of line-ending/stat behavior; its content matched HEAD during the last inspection. Verify with a content diff before treating it as a real K2 change.

No GitHub push is intended for v35 unless the user explicitly requests it after a successful live test.

---

## 4. End-to-end reconnect architecture

The working path crosses four layers:

```text
HoN client
  |  login/reconnect metadata + stock reconnect probe
  v
ThorGor master/account store
  |  authenticated account, active match, slave endpoint
  v
ThorGor UDP game gateway
  |  fresh per-client upstream transport + localized C0 identity
  v
K2 dedicated host (k2.dll)
  |  stable authenticated account on CClientConnection
  v
game.dll CGameServer
     retained CPlayer -> hero -> input/snapshot/host migration
```

Each layer has a distinct responsibility. Do not solve a game.dll lookup problem by changing browser/login identity, and do not solve a K2 transport problem by mutating the game player map.

### 4.1 Master and persistent reconnect metadata

Relevant files:

- `master/accounts.py`
- `master/server.py`

The SQLite account store keeps a reconnect record keyed by ThorGor `account_id`:

```text
account_id -> server_session, IP, port, match_id
```

Important behavior:

- `set_reconnect` validates the server session and active match before storing an endpoint.
- Login returns reconnect metadata only when the stored match ID equals the currently active match ID.
- `clear_reconnects` clears stale state.
- The reconnect record survives the chat/login session being dropped.
- Account cookies are deterministic local identities: `THORGOR_LOCAL_COOKIE_%08d`.

The master `host_release` endpoint is not the cause of the slave shutdown. It releases only an idle/pending host reservation. Logs from the creator-departure test showed the native slave resetting/exiting immediately after the client disconnect while the backend handler performed no destructive running-match action.

Do not “fix” creator departure by making `host_release` kill, recreate, or transfer the running slave.

### 4.2 Stock reconnect availability probe

Relevant file: `protocols/game_protocol.py`

The gateway recognizes the stock probe beginning with:

```text
00 00 01 CC
```

It parses the match ID, account ID, and connection ID, then replies with:

```text
00 00 01 6F + remaining grace period in milliseconds
```

The current grace period is 300 seconds. The response is emitted only when:

- the requested match is the active match;
- the authenticated account has a retained disconnect deadline; and
- the deadline has not expired.

This is what makes the stock reconnect dialog and countdown appear after relogin. Earlier symptoms where the dialog did not appear were upstream of native game admission.

### 4.3 UDP route retention and fresh transport

Relevant files:

- `protocols/game_protocol.py`
- `protocols/routing.py`
- `protocols/transport.py`

The gateway maintains independent per-client upstream UDP sockets. Session-unique loopback source addresses/ports prevent two local clients from collapsing into one K2 peer.

On client disconnect (`00 00 01 C3`):

1. Forward the final disconnect to K2.
2. Preserve the authenticated cookie and route identity for the grace period.
3. Preserve proxy-only team, slot, and player metadata.
4. Retire the old client route rather than immediately forgetting the identity.

On reconnect:

1. Authenticate the C0 against the master.
2. Recognize the cookie as a retired route.
3. Open a genuinely fresh K2 UDP transport before releasing the old route.
4. Carry the authenticated account marker to the paired K2 patch.
5. Restore proxy metadata.

The fresh upstream transport is essential even if the public client endpoint happens to be reused. Reusing the old K2 transport created ambiguous or stale native connection state in earlier attempts.

### 4.4 Localized C0 account identity

Relevant file: `protocols/transport.py`

For local admission, the gateway rewrites the native account field to a stable negative signed value:

```text
0x80000000 | ThorGor account_id
```

For a gateway-authenticated reconnect only, it temporarily adds:

```text
0x40000000
```

The paired K2 patch consumes and removes that private reconnect marker before game.dll sees the final account identity.

Rules:

- Never use the reconnect marker/nonzero reconnect token for initial admission.
- Never derive creator authority from untrusted client packet bits.
- Preserve the authenticated account across the new transport.
- Preserve the original creator authority semantics in the proven K2 build.

### 4.5 K2 authenticated identity and creator authority

Relevant files:

- `patches/builders/creator_authority.py`
- `patches/catalog_data/dedicated.creator_authority.json`
- `tests/test_lobby_authority.py`
- `tests/test_native_lobby_authority.py`

The proven patch:

- captures the parsed account early at K2 RVA `0x2F555C` into private stack storage (`[ebp-0x2c8]`) before retail code reuses its original local;
- later stores the normalized account at the authority hook near RVA `0x2F5AD6`;
- removes the private reconnect marker at RVA `0x2F5982`;
- uses authority cave RVA `0x70D740`;
- uses capture cave RVA `0x70D780`;
- disables AuthSuccess fallback promotion at RVA `0x2F8E1E`;
- disables the local-admission account reset at RVA `0x2F8E50`;
- restores creator low authority bits to `0x7` for the authenticated creator;
- clears those low authority bits for ordinary joiners.

The account must be captured early because the retail stack locals are reused:

- `[ebp-0x18]` begins as a parsed connection token, then becomes version state and later a client allocation pointer.
- `[ebp-0x48]` begins as account ID, but overlaps the map-insertion boolean output beginning at `[ebp-0x4c]`.

Reading either original local late caused different users to be stored with the same native account identity and made player2 reconnect select the host.

### 4.6 game.dll retained-player model

After a successful reconnect, v32 intentionally has two number domains:

```text
player-map key                  = historical client number
CPlayer + 0x6C                 = fresh live reconnect client number
```

Example from the working two-player path:

```text
retained player2 map key       = 1
retained player2 CPlayer+0x6C  = 2 after reconnect
```

This asymmetry is deliberate. Attempts to rekey the player map corrupted iterators, ownership, and host state. The safe design leaves the retained object and map topology intact, then adds narrow stock-first fallbacks only at call sites that consume current real-time packets.

Known fields:

| Object/field | Meaning |
|---|---|
| `CPlayer+0x6C` | current live native client number |
| `CPlayer+0x258` | stable native account ID |
| `CPlayer+0x254` | player entity pointer |
| `CPlayer+0x254 -> +0x23C` | player-entity live client number |
| `CPlayer+0x35A`, bit `0x1` | disconnected state |
| `CPlayer+0x35A`, bit `0x40` | connected transition |
| `CPlayer+0x3A4` | disconnect deadline; connected value is `UINT32_MAX` |
| `IHeroEntity+0x444` | hero owner/client number |

The stable identity is the authenticated account. The fresh client number is a transport/runtime identifier. The historical map key is an internal container key that cannot safely be rewritten in place during the retail reconnect callback.

---

## 5. The live-proven v32 game.dll repair chain

The manifest `patches/catalog_data/dedicated.reconnect_client_identity.json` is authoritative. `patches/builders/reconnect_client_identity.py` is primarily documentary/validation glue when explicit manifest operations are present; do not assume changing that builder alone changes the emitted DLL.

### 5.1 Account-selected retained player

The reconnect identity path finds the retained player by authenticated native account, not by username, route order, or the first map entry. The manifest anchors the stock predicate around RVA `0x333A3`, hooks the success path near `0x333DD`, and uses code fragments in the executable padding range `0x15691` through `0x15756`.

The PE section virtual size at file offset `0x1F0` is expanded from:

```text
F02A0700 -> 002E0700
```

This makes the later code caves executable/addressable in the loaded image.

### 5.2 Gameplay command fallback (v29)

Hook:

```text
game.dll RVA 0x47907 -> cave RVA 0x73B00
```

`CGameServer::ProcessGameDataFromClient` first performs the stock historical-key lookup. Only on a stock miss does the cave walk retained player values and select a unique `CPlayer` whose live `+0x6C` equals the packet sender.

This is why movement and ability commands reach the right hero without altering lobby admission or the shared player map.

### 5.3 Native connected-state restoration (v31)

Hook from the proven reconnect branch:

```text
game.dll RVA 0x333DD -> cave RVA 0x73C00
```

The cave mirrors `CPlayer::Connected(unsigned int)` field effects:

1. Clear bit 0 at `CPlayer+0x35A`.
2. Set bit `0x40` at `CPlayer+0x35A`.
3. Set `CPlayer+0x3A4` to `0xFFFFFFFF`.

Before this repair, input reached the server but the frame loop treated the retained player as disconnected. The rejoiner received almost no normal deltas and a large catch-up burst about every five seconds, producing extreme latency and frame skipping.

### 5.4 Real-time client snapshot fallback (v32)

Hook:

```text
game.dll RVA 0x2DD32 -> cave RVA 0x73D00
```

`CGameServer::ProcessClientSnapshot` had its own historical-key lookup. When it missed for live number 2, the server emitted:

```text
Received snapshot with invalid client number 2
```

The v32 cave preserves the stock lookup and, only on miss, resolves a unique retained player by `CPlayer+0x6C`. This removed the snapshot error, the five-second input delay, and the remaining control latency.

These two narrow call-site fallbacks—gameplay dispatch and client snapshots—are the successful pattern. Do not generalize them into the shared map lookup.

---

## 6. Current creator-departure diagnosis

The creator-departure failure is not the reconnect admission path. It occurs when the current native host leaves and `CGameServer::RemoveClient` tries to choose a successor.

Function:

```text
game.dll RVA 0x32A80  CGameServer::RemoveClient
```

Observed behavior on the v32 baseline:

- player2 may have reconnected successfully and remain a valid connected retained `CPlayer`;
- its map key remains historical (for example 1);
- its live `CPlayer+0x6C` is fresh (for example 2);
- host migration reads `+0x6C`, then performs a stock player-map lookup by 2;
- that lookup misses because the node is still keyed by 1;
- stock migration rejects the otherwise valid connected player2 as a successor;
- with no successor, the slave shuts down the match.

This explains why changing creator authority flags did nothing: the failure is successor resolution, not whether the departing creator had too much authority.

---

## 7. v34 failure and v35 candidate

### 7.1 Why v34 crashed ordinary player2 disconnect

V34 tried to repair the host-migration miss inline. Its five-byte rewrite overlapped the first byte of an independent stock direct branch target at RVA `0x32FB2`.

Ghidra evidence:

```text
0x21032E6A  JZ  0x21032FB2
0x21032FB2  MOV EDX,[EAX+0xE8]
```

The v34 patch began near RVA `0x32FAE` and consumed the first byte at `0x32FB2`. When ordinary player2 disconnected, the stock branch jumped directly into corrupted code. The slave crashed before any reconnect attempt.

Crash evidence:

- dump: `C:\Users\Thor\Documents\Heroes of Newerth\game\crash_3.2.7.1_0035.dmp`
- time: 2026-09-19 17:44:03
- exception: `0xC0000005`
- EIP: garbage `0xDEFD9560`
- first useful return address: `game.dll+0x32E81`

This is a permanent patching lesson: disassembling only the fall-through block is insufficient. Before replacing bytes, enumerate every direct branch target into the whole range.

### 7.2 v35 isolated implementation

V35 removes the v34 inline rewrite.

Hook:

```text
RVA 0x32FA3
expected:    8B45503B87
replacement: E9E80D0400
```

Dedicated cave:

```text
RVA 0x73D90
expected:    24 zero bytes
replacement: 8B45503B870001000075088B5E10E92BF2FBFFE923F2FBFF
```

Semantics:

```asm
mov eax, [ebp+0x50]
cmp eax, [edi+0x100]
jne miss
; stock hit -> original hit destination at 0x32FCB

miss:
mov ebx, [esi+0x10]   ; reuse the CPlayer already being iterated
; continue at original miss/successor guards at 0x32FCE
```

The stock ordinary-disconnect target at RVA `0x32FB2` remains exactly:

```text
8B90E8000000
```

The native test both hash-checks and executes that instruction so a future patch cannot repeat v34 unnoticed.

V35 does not mutate:

- K2 admission;
- authenticated account identity;
- player-map keys or nodes;
- lobby slot/team assignment;
- hero ownership;
- gameplay command lookup;
- client snapshot lookup;
- connected-state fields;
- creator authority.

It changes only the host-migration map-miss path. This is the right scope, but it still requires live validation.

---

## 8. Complete experiment history and lessons

### Pre-v14 symptom phase

The earliest state had several different failures that should not be confused:

- no reconnect dialog after returning to menu or relogging;
- reconnect dialog present but immediate “No response from server” or “Connection error”;
- reconnect reached the slave but showed a black game area with menu/pre-match UI;
- other player did not see the stock reconnect timer/status;
- broad identity/lobby experiments temporarily caused wrong avatar/icon data, creator displacement, server-selection crashes, or player2 being forced to spectator.

The backend reconnect record, stock probe/reply, route retention, fresh upstream socket, and authenticated C0 work solved the dialog/routing portion. The remaining work then moved into native identity and retained player state.

### v14 — stable flow, wrong player

**Worked:** reconnect dialog, admission, match load, slave survival.  
**Failed:** player2 returned as `player`/creator, displaced or broke the host.  
**Lesson:** transport flow was viable, but retained-player selection used the wrong identity. Preserve this as the first end-to-end flow milestone, not a correct reconnect.

### v15 — forced native client-number reuse

**Attempt:** reclaim player2's old K2 number inside `CHostServer::GenerateClientID`.  
**Failure:** K2 still owned that number; duplicate registration killed the slave before game.dll admission.  
**Lesson:** never force number reuse while the old allocation/transport remains native-owned.

### v16 — atomic player-map rekey

**Attempt:** erase the historical player-map node and insert the retained player under the fresh number.  
**Failure:** the surrounding reconnect function still held an iterator/node pointer in EBX. Erasing the node left a dangling iterator, caused ownership swaps, and produced a delayed slave crash.  
**Lesson:** a container mutation can be locally correct but violate caller lifetime assumptions.

### v17 — rekey plus iterator transfer

**Attempt:** update the caller's saved iterator to the replacement node.  
**Result:** structurally sound in emulation, but live player2 inherited the host hero, the host received defeat, and the slave ended.  
**Lesson:** even a correct map rekey is the wrong layer. Retain the historical map topology.

### v18 — persistent nonzero token from initial admission

**Attempt:** give the client one stock-style nonzero token from first admission through reconnect.  
**Failure:** creator admission crashed before K2 assigned a native client number.  
**Lesson:** initial local admission must use the stock zero-token allocation path. Reconnect-only markers must never appear on first admission.

### v19 — retired-number reclaim and register corruption

**Attempt:** reconnect token encoded the observed original native number; K2 reclaimed the retired allocation after account/state validation.  
**Failure:** hook at K2 `+0x2F5AD6` clobbered EDX, which held the C0 packet pointer. `CPacket::ReadInt` treated client number `-1` as a vtable and read near `0x4F`.  
**Dump:** `crash_3.2.7.1_0029.dmp`, access violation at `k2.dll+0x286B2B`, reached from `+0x2F8C26` / C0 admission near `+0x2F5ADE`.  
**Additional discovery:** late stack locals no longer contained the parsed account/token.  
**Lesson:** preserve every live register and capture parsed identity before retail reuses stack storage.

### v20 — early capture, stale string crash

**Worked:** private stack slots captured account/token early; register preservation corrected v19.  
**Failure:** native reconnect lookup compared an incoming address against `CClientConnection+0x1AC` on a destroyed/stale transport string. C++ raised `invalid string position`.  
**Location:** `k2.dll+0x78A6`, called from `+0x70D50D` and ReadPackets near `+0x2F5DC2`.  
**Lesson:** do not dereference transport strings before cheap state and identity rejection.

### v21 — state-zero skip

**Attempt:** skip state-zero retired transports before string comparison.  
**Failure:** the live host record could still reach the unsafe comparison even though its token did not match.  
**Lesson:** predicate order matters. Reject unrelated token/account candidates before touching stateful address data.

### v22 — token-first/state-first lookup

**Worked:** token mismatch short-circuited first, state check next, address comparison last. This prevented the observed string crash and preserved correct identity snapshots.  
**Limitation:** the native-number reclamation design still did not produce the final stable reconnect behavior.  
**Lesson:** safe lookup order is token/account, state, then expensive/stale-prone fields.

### v23 — rollback to v14 flow baseline

**Action:** removed the brittle reclamation path and restored the known flowing admission model; enabled passive native identity tracing.  
**Result:** stable flow returned, still wrong player.  
**Lesson:** return to the last known flow boundary before layering new identity evidence.

### v24 — early authenticated account capture

**Discovery:** both retained players could contain account 1 because K2 read a reused local.  
**Fix:** capture authenticated account before reuse and store the normalized value.  
**Live result:** player2 rejoined as the correct player; host was not displaced; slave remained alive; map loaded. No hero control.  
**Tag:** `reconnect-v24-correct-player-milestone`.  
**Lesson:** account identity, not client number or map order, must choose the retained player.

### v25 — hero owner update

**Attempt:** update `IHeroEntity+0x444` to the fresh live number.  
**Result:** correct hero ownership display, but no movement/ability control.  
**Lesson:** ownership and packet dispatch are distinct stages.

### v26 — shared player-map miss fallback

**Attempt:** make the common lookup fall back from historical key to live `CPlayer+0x6C`.  
**Failure:** shared lookup is also used during normal lobby admission; ordinary joins became spectators or otherwise broke lobby slot behavior.  
**Lesson:** never globally change shared map semantics to solve a reconnect-only packet path.

### v27 — phase-gated shared fallback

**Attempt:** gate the common fallback by game phase.  
**Failure:** still too broad and caused lobby/spectator regressions.  
**Lesson:** patch the exact consumer, not a common helper, even when a phase check appears safe.

### v28 — player-entity live number

**Fix:** update `CPlayer+0x254 -> +0x23C` while keeping the map key historical.  
**Live result:** correct player and hero, stable host/slave, no control.  
**Tag:** `reconnect-v28-correct-player-no-control-milestone`.  
**Lesson:** entity ownership was necessary but did not resolve the dispatcher's own map lookup.

### v29 — gameplay dispatcher fallback

**Fix:** narrow stock-first fallback only in `CGameServer::ProcessGameDataFromClient`.  
**Live result:** movement and abilities reached the correct hero; host remained connected. Assets were missing for roughly 3–5 seconds, followed by extreme latency and frame skipping.  
**Tag:** `reconnect-v29-control-restored-latency-wip`.  
**Lesson:** narrow consumer-local fallback is safe; residual latency was server connection state, not input routing.

### v30 — team/roster mutation

**Attempt:** call reconnect-time team roster methods to restore state delivery.  
**Failure:** slave crash.  
**Lesson:** never call retail team/roster mutation methods from the reconnect callback without proving their phase and object invariants. This experiment is rejected.

### v31 — native connected-state restoration

**Fix:** clear disconnected bit, set connected-transition bit, and set deadline to `UINT32_MAX`.  
**Live result:** severe latency mostly disappeared; correct player stayed connected. However the slave spammed `Received snapshot with invalid client number 2`, with about a five-second delay before effective controls.  
**Lesson:** per-frame connection state and snapshot sender resolution are separate.

### v32 — client snapshot fallback

**Fix:** narrow stock-first fallback in `CGameServer::ProcessClientSnapshot` by live `CPlayer+0x6C`.  
**Live result:** perfect player2 reconnect in the observed test: right player/hero, host stable, slave stable, immediate controls.  
**Commit:** `4e9c9c0`.  
**Lesson:** this is the safe baseline. Any creator-departure fix must preserve these exact paths.

### v33 — reduced creator authority flags

**Hypothesis:** creator departure killed the slave because low authority flags `0x7` prevented migration.  
**Attempt:** reduce creator low flags from `0x7` to `0x1`.  
**Live result:** creator still killed the slave.  
**Lesson:** authority flags were not the root cause. Restore proven K2 hash `BA14...`.

### v34 — inline host-migration fallback

**Hypothesis:** correct; migration could not find a reconnected successor by fresh live number.  
**Implementation:** unsafe; five-byte inline rewrite overlapped direct target RVA `0x32FB2`.  
**Live result:** player2 disconnect itself killed the slave before reconnect.  
**Lesson:** the idea and byte placement must be evaluated separately. Never reuse this binary.

### v35 — isolated host-migration cave

**Implementation:** detour at `0x32FA3`, cave at `0x73D90`, stock target `0x32FB2` intact and executable-tested.  
**Automated result:** full 74-test suite passed in source and packaged output at the time it was built.  
**Live result:** not yet established.  
**Next action:** run the exact acceptance sequence; do not add more changes before observing v35 live behavior.

---

## 9. Regressions that must not return

These are hard constraints for future work:

1. **Do not rekey or erase player-map nodes during reconnect.** The retail caller retains iterators and other systems assume historical topology.
2. **Do not force native client-number reuse** while an old allocation or transport remains native-owned.
3. **Do not put a nonzero reconnect token/marker on initial admission.**
4. **Do not read late K2 stack locals** for account or token; they are reused.
5. **Preserve EDX and all live registers** around C0/K2 hooks unless disassembly proves otherwise.
6. **Do not touch connection address strings** until token/account and state checks establish that the record is relevant and alive.
7. **Do not change the shared player-map lookup.** It affects lobby admission and caused spectator regressions.
8. **Do not call team/roster methods** from reconnect state restoration.
9. **Do not broaden lobby, slot, avatar, or spectator behavior** while fixing in-match reconnect.
10. **Do not patch across a branch target.** Enumerate incoming references and disassemble the full overwritten range first.
11. **Do not trust unit tests alone.** Native emulation proves instruction behavior, not full retail object lifetime or phase correctness.
12. **Do not test with an old match.** A running slave contains objects created and mutated by the prior build.
13. **Do not interpret a live test without binary hashes and timestamps.**
14. **Do not push experimental iterations** unless the user explicitly asks. Keep local candidates local until live-proven.

---

## 10. Instrumentation and evidence

### Runtime files

Under the runnable package:

- `var/ThorGor_SESSION_*.zip` — bundled logs for a whole run.
- `var/dashboard_logs/*.log` — component logs.
- `var/work/reconnect_identity_events.jsonl` — read-only native player-map identity snapshots.
- `var/work/native_matchid_bridge_v47.log` — native bridge diagnostics.
- `var/work/manager_status_bridge_v42.log` — process/status bridge diagnostics.
- `var/work/v31_registration_state.json` — connection-state instrumentation from the v31 path.

The identity trace should be treated as observation only. It must never mutate the game process.

### Important captured session

V34 failure bundle:

```text
C:\Users\Thor\Documents\Codex\2026-09-17\we\outputs\ThorGor-HoN-3.2.7\var\ThorGor_SESSION_20260919_174421.zip
```

Creator-departure timing from an earlier v32 session (match 19):

```text
17:24:03.777 creator sent backend host_release
17:24:03.909 slave control reset/exited
```

The backend handler did not destroy the match; native departure logic did.

### Minidump inspection

Tool:

```text
tools/minidump_inspect.py
```

It reports exception code/address, register values, loaded modules, and stack pointers/return addresses. Always map addresses to module RVAs before changing a patch.

Known dumps:

| Dump | Build | Finding |
|---|---|---|
| `crash_3.2.7.1_0029.dmp` | v19 | EDX packet pointer clobbered; crash in `CPacket::ReadInt` |
| `crash_3.2.7.1_0032.dmp` | v20/v21 era | `invalid string position` during stale address comparison |
| `crash_3.2.7.1_0035.dmp` | v34 | inline patch overwrote direct target `game.dll+0x32FB2` |

For any future crash, preserve the dump, exact wall-clock test time, session zip, installed hashes, and the exact client action that preceded it.

---

## 11. Ghidra workflow

Ghidra installation:

```text
C:\intelprop\ghidra_11.4.3_PUBLIC
```

Saved analysis projects from the earlier workspace:

```text
C:\Users\Thor\Documents\Codex\2026-09-07\https-github-com-lightningfastcomputing-thorgor-hon-2\ThorGor-HoN-3.2.7\work\game_reconnect_trace
C:\Users\Thor\Documents\Codex\2026-09-07\https-github-com-lightningfastcomputing-thorgor-hon-2\ThorGor-HoN-3.2.7\work\k2_reconnect_trace
```

Programs used:

- game project: `game_reconnect_input.dll`
- K2 project: `k2.dll.thorgor_before_04aa0...`

Helper scripts:

```text
tools/ghidra/DecompileAt.py
tools/ghidra/DumpListing.py
tools/ghidra/FindRefs.py
tools/ghidra/FindInstructions.py
```

Typical headless pattern:

```powershell
& 'C:\intelprop\ghidra_11.4.3_PUBLIC\support\analyzeHeadless.bat' `
  '<project-directory>' game_reconnect_trace `
  -process game_reconnect_input.dll -noanalysis `
  -scriptPath '<active-source>\tools\ghidra' `
  -postScript DumpListing.py 0x21032FA0 80
```

Configured JDK:

```text
C:\Program Files\Eclipse Adoptium\jdk-25.0.1.8-hotspot
```

Saved Ghidra Java setting:

```text
%APPDATA%\ghidra\ghidra_11.4.3_PUBLIC\java_home.save
```

### Mandatory binary-patch review

Before accepting a new hook:

1. Confirm the correct input SHA-256.
2. Dump at least the containing basic block and neighboring blocks.
3. Find all direct and indirect references into every byte being overwritten.
4. Check whether any byte is a branch destination, exception boundary, switch target, or function entry.
5. Identify register and flag liveness at both the hook and return destinations.
6. Use an isolated cave when the inline space is not unquestionably safe.
7. Pin expected input bytes in the manifest.
8. Pin the full output SHA-256.
9. Add a native test that executes both new and preserved paths.
10. Disassemble the final emitted binary, not merely the intended byte sequence.

V34 passed conceptual review but failed steps 3 and 10. V35 exists specifically to correct that process failure.

---

## 12. Build, install, and test workflow

### Automated tests

The test environment needs `pefile` and `unicorn`; the normal ThorGor runtime does not.

Known dependency path:

```text
<source>\work\native-test-deps
```

Example:

```powershell
$env:PYTHONPATH = 'C:\Users\Thor\Documents\Codex\2026-09-17\we\ThorGor-HoN-3.2.7\work\native-test-deps'
$env:THORGOR_TEST_HON_HOME = 'C:\Program Files (x86)\Heroes of Newerth'
py -m unittest discover -s tests
```

The current v35 candidate passed 74 tests when built. Relevant native tests execute:

- K2 account capture/normalization;
- creator versus joiner authority;
- account-selected reconnect player;
- gameplay dispatcher live-number fallback;
- connected-state restoration;
- client snapshot live-number fallback;
- v35 host-migration stock hit and reconnect miss;
- exact preserved execution at RVA `0x32FB2`.

On 2026-09-24, a fresh verification attempt ran 63 non-native tests but could
not import `work/native-test-deps/pefile.py` because Windows denied read access
to that local dependency file. This was an environment/ACL failure, not a test
assertion or a new reconnect result. Repair or recreate the dependency folder,
then rerun the complete suite before changing the recorded 74-test status.

### Installer

Current candidate launcher:

```text
INSTALL_RECONNECT_V35.bat
```

It elevates when necessary, stops/cleans the old stack, installs and verifies the supported patches, resets volatile state, and starts the dashboard from the active package.

All HoN clients and dedicated processes must be closed before installation. If `hon.exe` or a slave still holds a DLL open, installation fails with:

```text
PermissionError: [WinError 5] Access is denied
```

That is a file-lock problem, not reconnect evidence.

`patches/installer.py` rebuilds from verified stock backups and accepts only known input/output hashes. Never hand-copy a DLL over an unknown installed state and then call the result reproducible.

### Pre-live-test checklist

1. Close both HoN clients and every slave process.
2. Run the intended numbered installer from the intended package.
3. Verify installed `k2.dll` and `game\game.dll` hashes.
4. Clear old volatile match/reconnect state through the installer.
5. Start a completely new match.
6. Confirm both players can join normal slots; neither is forced to spectator.
7. Confirm server selection and Create Game work before testing reconnect.
8. Record the wall-clock time of every disconnect and reconnect click.
9. If a failure occurs, leave the stack running so logs and process state can be inspected.

---

## 13. How to reason about symptoms

| Symptom | Most likely stage |
|---|---|
| No reconnect dialog | master reconnect record, active match ID, or CC/6F probe path |
| Dialog appears, instant connection error | endpoint/routing/C0 admission or slave unavailable |
| Other player never sees reconnecting timer | disconnect not forwarded/retained correctly or admission never reached game |
| Black game area with menu/pre-match lobby | admitted to server but not attached to the retained in-progress player/session |
| Rejoiner becomes host/player1 | wrong native account capture or first-entry retained-player selection |
| Host is kicked/defeated when player2 returns | player-map mutation or wrong retained-player/hero ownership |
| Correct hero visible, cannot move/level | gameplay dispatcher lookup or owner/entity live number |
| Controls work only after ~5 seconds; frame skipping | retained `CPlayer` still marked disconnected in frame loop |
| `invalid client number 2` snapshot spam | `ProcessClientSnapshot` historical-key lookup missing fresh live number |
| Joiner forced to spectator before match | shared player lookup/lobby authority was broadened; revert it |
| Player2 disconnect immediately crashes slave | ordinary disconnect path corrupted; verify v34 is not installed and inspect `0x32FB2` |
| Creator disconnect kills otherwise running slave | host-successor migration cannot resolve retained connected player |

This table is diagnostic, not permission to patch the first matching function. Confirm with logs, hashes, and native traces.

---

## 14. Required live acceptance sequence for v36

Do not make another code change before running this sequence on a fresh match:

1. Start the stack with verified v36 hashes.
2. Launch `player` and create a two-player game.
3. Join with `player2`; confirm both occupy normal player slots.
4. Start the match and move/level abilities on both clients.
5. Disconnect player2.
6. Confirm the slave remains alive and player sees the disconnect/grace state.
7. Relog player2 and reconnect.
8. Confirm player2 returns to player2's original hero with immediate movement and ability control.
9. Confirm `player` remains connected and controllable.
10. Now disconnect creator `player` while player2 remains in the match.
11. Confirm the slave remains alive and player2 continues controlling player2's hero.
12. Relog creator `player` and reconnect.
13. Confirm creator returns to the creator's original hero with immediate control.
14. Repeat one disconnect/reconnect cycle to catch stale-route state.
15. Continue playing beyond the previous delayed-crash window.

Pass criteria are all-or-nothing. A surviving slave with broken ownership is not a pass; a correct reconnect that corrupts normal player2 departure is not a pass.

### If v36 fails

- If player2 disconnect crashes before reconnect, first verify that the installed game hash is really v36 and that RVA `0x32FB2` is stock. Do not extend the host-migration patch.
- If player2 reconnect regresses, roll back to v32 immediately and diff only v35/v36 host-migration operations.
- If player2 works but creator still exits, instrument `CGameServer::RemoveClient` read-only:
  - departing native number/account;
  - current host number;
  - every candidate map key;
  - candidate `CPlayer+0x6C`, `+0x258`, `+0x35A`, and connection pointer/state;
  - whether the v35 cave executes;
  - which stock guard rejects the candidate;
  - whether shutdown is selected afterward.
- If host migration succeeds but creator reconnect fails, keep migration and returning-creator admission as separate investigations. The original creator should regain the original retained player/hero; do not automatically re-promote creator authority unless retail behavior proves that is required.

---

## 15. Recommended next coding steps

### Immediate step: no code change

Live-test v36 exactly as packaged. Its purpose is to answer one question: can
game-side host migration accept the already-iterated connected retained player
when K2 cannot resolve the fresh number, without damaging ordinary disconnect
or v32 reconnect?

### If additional instrumentation is required

Prefer read-only telemetry in `game_manager/native_match_id.py` or a debugger trace. Log identities and branch decisions; do not repair state from the bridge.

The highest-value trace is a single `RemoveClient` event record containing:

```json
{
  "event": "remove_client_host_migration",
  "leaving_client": 0,
  "leaving_account": "0x80000002",
  "old_host": 0,
  "candidate_map_key": 1,
  "candidate_live_client": 2,
  "candidate_account": "0x80000003",
  "candidate_flags": "0x0040",
  "candidate_connection": "non-null",
  "lookup_hit": false,
  "v35_fallback_used": true,
  "stock_guard_result": "accepted or reason",
  "new_host": 2,
  "shutdown_selected": false
}
```

Addresses/pointers may be included for correlation, but the stable diagnostic fields are account, historical key, live number, flags, and branch decision.

### If v35 passes

1. Freeze a Git commit and tag before cleanup/refactoring.
2. Store final DLL hashes in the manifest and guide.
3. Copy the verified package to outputs.
4. Push only after the user explicitly requests it.
5. Update this document from “candidate” to “live-proven,” including the exact test time and session bundle.

---

## 16. Files a new engineer/LLM should read first

Read in this order:

1. `RECONNECT_TECHNICAL_HANDOFF_2026-09-24.md` — this document.
2. `docs/RECONNECT.md` — detailed implementation history and current patch explanation.
3. `Reconnect-v35-notes.md` — concise current candidate notes.
4. `patches/catalog_data/dedicated.reconnect_client_identity.json` — authoritative game.dll operations and hashes.
5. `patches/catalog_data/dedicated.creator_authority.json` — authoritative K2 identity patch metadata.
6. `patches/builders/creator_authority.py` — K2 account/authority stubs.
7. `protocols/transport.py` — localized authenticated C0 identity.
8. `protocols/game_protocol.py` — reconnect probe, route retention, fresh transport, proxy telemetry.
9. `master/accounts.py` and `master/server.py` — persistent reconnect record and login response.
10. `game_manager/native_match_id.py` — read-only native identity/status trace.
11. `tests/test_native_lobby_authority.py` — executable instruction-level regression coverage.
12. `tests/test_native_match_id.py`, `tests/test_lobby_authority.py`, and `tests/test_browser_occupancy.py` — cross-layer behavior.

Do not start from old numbered installers as architectural truth. They are historical artifacts and may reference older workspaces or rejected binaries.

---

## 17. Compact identity invariants

Any future reconnect build must satisfy all of these simultaneously:

```text
ThorGor account identity is stable across login/chat/UDP transport loss.
The reconnect endpoint belongs to the active match and authenticated account.
The returning client receives a fresh UDP/K2 transport.
Initial admission uses stock zero-token allocation.
K2 stores the early parsed authenticated account, not a reused local.
The retained CPlayer is selected by authenticated account.
The retained player-map node/key is not erased or rekeyed.
CPlayer+0x6C becomes the fresh live native client number.
Player entity +0x23C becomes the fresh live native client number.
Hero owner +0x444 becomes the fresh live native client number.
CPlayer connected flags/deadline are restored.
Gameplay packets resolve stock-first, then narrowly by live +0x6C.
Client snapshots resolve stock-first, then narrowly by live +0x6C.
Lobby/shared lookup remains stock.
Host migration accepts a connected retained player even when live number != map key.
The original host is not displaced by player2 reconnect.
Ordinary player2 disconnect remains safe.
Creator departure does not shut down the match when a valid successor exists.
```

If a proposed change violates any one of these, it is a redesign and must be justified with new evidence—not treated as a small reconnect fix.

---

## 18. Ready-to-use continuation prompt

The following prompt can be given to another coding model together with this repository:

> Continue ThorGor HoN 3.2.7 reconnect work from the documented state. Read `RECONNECT_TECHNICAL_HANDOFF_2026-09-24.md`, `docs/RECONNECT.md`, the reconnect manifest, and native tests before editing. Treat commit `4e9c9c0`/v32 as the last live-proven baseline: player2 reconnects as the correct player with immediate control and without displacing the host. The only confirmed v32 defect is that original creator departure shuts down the slave. The local working tree contains v35, an uncommitted isolated host-migration candidate. V34 is rejected because it overwrote the independent stock branch target at game.dll RVA `0x32FB2` and made ordinary player2 disconnect crash. Do not rekey the player map, reuse native client IDs, modify shared lobby lookup, call team/roster mutation methods, or change K2 creator flags. First verify hashes and live-test v35 on a fresh two-client match using the acceptance sequence in the handoff. If it fails, preserve the stack, dump, timestamps, and session logs; instrument the host-migration candidate/guard decisions read-only before making another patch. Do not push experimental work unless explicitly requested.

---

## 19. Final perspective

The reconnect problem is now mostly understood and mostly solved. The difficult boundary was crossed at v32: a returning transport can be authenticated, mapped to the correct retained player and hero, marked connected, and accepted by both real-time command and snapshot paths without disturbing the host.

The remaining creator-departure issue is narrower. It is a host-migration successor lookup that still assumes the retail invariant “map key equals live client number,” while successful reconnect intentionally breaks that invariant. The correct continuation is to repair only that consumer while preserving every live-proven v32 behavior. V35 is the first candidate designed with that exact scope and with the v34 branch-target regression explicitly guarded.
