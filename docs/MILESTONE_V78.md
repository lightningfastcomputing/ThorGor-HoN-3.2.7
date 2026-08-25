# v78 joiner team-chat delivery — 2026-08-24

Two-client route traces proved that the host and joiner both receive the same
reliable game-chat events. Team messages use payload subtype `0x02`; all-chat
uses subtype `0x03`. The failure therefore occurs after transport delivery.

The HoN 3.2.7.1 `cgame.dll` handler at image address `0x19108220` resolves the
sender's replicated `CPlayer`, then—under the client's normal chat filter—drops
the event when the local team field differs from the sender's field. A joiner's
replicated sender-team field can remain stale even though the dedicated server
has already selected that joiner as a legitimate team-message recipient.

`client.team_chat_delivery` adds a narrow subtype guard. Server-authorized team
chat (`0x02`) bypasses only the stale local-versus-sender team comparison. The
existing ignored-player check, mute modes, sender lookup, all-chat path, and all
other message subtypes retain their original instructions.

Verified cgame SHA-256:

`1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF`
