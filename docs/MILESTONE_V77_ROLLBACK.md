# v77 rollback after two-client match-transition failure — 2026-08-24

## Observed failure

Two clients completed lobby admission and hero selection, then exited together
during the `5 4 3 2 1` picking-to-game transition. The shared HoN console ended
abruptly during the countdown and produced no HoN Windows Error Reporting event.

The session bundle was captured as
`ThorGor_SESSION_20260824_123911.zip`. Its manager bridge remained connected
until the stack was manually closed. The HoN match log recorded both players,
and the installed K2 hash was the v77 tail-recipient build
`25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026`.

## Support decision

v77 is no longer installed automatically. Its tail-recipient hero-state path is
retained in the declarative catalog for reversing and crash-forensics work.
The supported installer now restores the verified v65 linked-delivery baseline:

`82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB`

cgame v61 remains supported and unchanged:

`88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`

When rolling back an installed v77 binary, the installer preserves it as
`k2.dll.thorgor_experimental_v77`.

## Next verification

Repeat the same two-client match using v65. Prioritize successful transition
into Caldavar over joined-client hero portrait completeness. Capture separate
per-process client logs before attempting another recipient-state patch.
