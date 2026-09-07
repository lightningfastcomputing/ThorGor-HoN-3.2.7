# Creator-only lobby authority

Baseline: `refactored-architecture-2026-08-24`, commit
`47bfd862f0130dbb87aebcbc4867ed85f4f4caec`.

The creator's star and controls were correct, but joiners also appeared as
hosts. The source is native connection authority, which drives both the
`NETCMD_GAME_HOST` event and the lobby player state. Changing button visibility
alone would leave server authority wrong.

## Verified native paths

- K2 RVA `0x2F5AD6`: local admission grants composite local/admin/host flags.
- K2 RVA `0x2F8E1E`: an AuthSuccess fallback can promote a joiner again.
- K2 RVA `0x2F8E27`: bit zero controls native `0x69,1` game-host emission.
- The C0 byte at `[ebp-0x11]` is the native host-request marker.

The authority patch removes the marker rejection at `0x2F5982`, replaces the
flag assignment with a bounded cave at `0x70D740`, and removes the fallback
promotion. The cave clears low bits 0-2 and restores them only when marker bit
zero is set. Higher connection flags and the existing linked-client hero-state
code remain intact.

## Backend and proxy

Every `c_conn` response contains a typed `is_match_host` integer. A pending or
active owner must match both the authenticated account and key; a normal JOIN
receives zero. The proxy rejects missing or ambiguous authority responses and
overwrites only the marker's low bit with the backend decision. Reservation
updates are serialized so concurrent C0 requests cannot displace an owner.

The master, proxy, and K2 patch are a paired change and must be deployed
together. Creator reconnect with the original key retains authority; an
empty-key JOIN remains an ordinary player.

## Capacity dependency

The verified retail `game.dll` has a one-client capacity callback at RVA
`0x529E5` and an inlined comparison at `0x337EC`. Host misclassification hid
that limit. Both values are changed to ten so ordinary joiners can enter a
normal five-versus-five lobby.

## Reproducibility

- K2 input: `25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026`
- K2 output: `21AD692656419D6483DE1B93A16DFB7E04BC7C2ACB6EBDA00D6F7A54A13493F0`
- game.dll input: `D345F8537ED9FD5C6705F8F1A9FA6663C5F4AE4476CD328B2D8F1074C044CF99`
- game.dll output: `929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B`

The installer rebuilds and verifies candidates before replacement, preserves
the previous bytes, and rejects unknown inputs. Binary files are not stored in
the repository.

## Validation

Automated tests cover backend owner selection, proxy encoding, all 256 input
marker values, native x86 host-event behavior, capacity, exact hashes,
idempotence, and backup preservation. The live check covers creator star and
controls, joiner ordinary icon and no host controls, replicated creator actions,
hero selection, and match start. Existing cgame/game_shared crash investigations
remain separate.

On 2026-09-07, the user confirmed that this paired backend/proxy/native build
worked in live client testing. A recorded repetition of the full creator/joiner
operation matrix remains recommended for future regression evidence.
