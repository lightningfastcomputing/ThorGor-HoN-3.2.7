# v78 joiner team-chat experiment — REJECTED (2026-08-24)

Two-client route traces proved that the host and joiner both receive the same
reliable game-chat events. Team messages use payload subtype `0x02`; all-chat
uses subtype `0x03`. The failure therefore occurs after transport delivery.

The HoN 3.2.7.1 `cgame.dll` handler at image address `0x19108220` resolves the
sender's replicated `CPlayer`, then—under the client's normal chat filter—drops
the event when the local team field differs from the sender's field. A joiner's
replicated sender-team field can remain stale even though the dedicated server
has already selected that joiner as a legitimate team-message recipient.

The bounded client experiment bypassed only that comparison for subtype `0x02`.
A live retest with the exact patched hash still failed. This proves the event is
discarded earlier, while resolving the sender's missing `CPlayer` record. The
patch is removed from the supported catalog and retained only in Git history.

The same retest exposed the upstream cause: real creators set the C0 external
identity bit, while joiners do not. ThorGor's compatibility bridge then cleared
that bit for every connection, selecting K2's local-host path for everyone.
The supported fix now keeps every backend-approved identity on K2's external
admission path so the full player record is constructed.

Rejected cgame SHA-256:

`1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF`
