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

The same retest exposed a correlation: real creators set the C0 external
identity bit, while joiners do not. An experiment kept every backend-approved
identity on K2's external path. K2 immediately returned
`rejected_invalid_request` before making a native master request, including for
an otherwise valid creator packet. The bit is therefore not a generic switch
for full player identity; it belongs to an external-authentication contract
ThorGor has not reconstructed. The supported bridge continues to use K2's
local-admission path after validating the account with ThorGor's master service.

The incorrect multi-host presentation and missing joiner team chat remain an
upstream player-registry problem. Neither rejected experiment is shipped as a
fix.

Rejected cgame SHA-256:

`1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF`
