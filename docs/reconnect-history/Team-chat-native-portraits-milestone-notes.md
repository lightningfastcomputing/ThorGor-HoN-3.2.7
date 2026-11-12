# Team-chat native portraits milestone

Frozen on 2026-09-27 from `refactored-architecture-reconnect-wip`.

## Preserved baseline

- Reconnect v39 behavior is unchanged.
- Creator and joiner reconnect handling remains on the frozen reconnect path.
- Ordinary all chat remains unchanged.

## Observed behavior before this candidate

- Native host team chat displayed HoN's stock yellow `[T]` label and portrait.
- Mirrored joiner team chat displayed `[TEAM]` and omitted hero portraits.
- All chat displayed the correct hero portraits for host, player2, and player3.

## Live evidence

The 2026-09-27 packet log assigned native client number `1` to player2 and `2`
to player3. The joiner team-chat relay then replaced both identities with sender
number `0`, which is the creator. That discarded the native sender identity HoN
already uses successfully to resolve portraits in all chat.

## Frozen changes

- Normalize mirrored team chat to the stock `[T]` label.
- Preserve the server-assigned native sender number in mirrored team-chat events.
- Retain the authenticated sender name and slot color in the ThorGor marker.
- Supply authenticated sender metadata when converting direct joiner team-chat
  events.
- Keep the previous Lua portrait cache as a compatibility fallback without
  replacing a valid native portrait entity.

## Validation

- 20 focused team-chat tests pass.
- 64 broader non-native tests pass.
- The generated seven-entry UI overlay applies cleanly to the stock HoN 3.2.7.1
  resource archive.
- Source and runnable output package files have matching SHA-256 hashes.

The final native-sender portrait change is frozen as a testable milestone but
still requires a live three-client confirmation after reinstalling the overlay.
