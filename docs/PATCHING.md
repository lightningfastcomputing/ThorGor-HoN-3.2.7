# Source-only patching

The repository intentionally distributes patch logic, hashes, and documentation—not game binaries.

## Verified inputs

- Genuine clean HoN 3.2.7.1 `k2.dll`: `04AA0DBCC88A86AD8D7C5429A24CE79A62DBB8C40B552AC629D0D76079254095`
- Legacy localhost-normalized HoN 3.2.7.1 `k2.dll`: `8929AE8993AF41AE9F63BEE43DAB27402205621CFFC57F8ACC8DB0C4FB95FAE9`
- Stock HoN 3.2.7.1 `game\cgame.dll`: `45B3CE39214EFD82D12DA8B01E73494CEE983D6DB4891C7D95DF10B2EAA70B02`

## Verified outputs

- K2 v57 baseline: `6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF`
- K2 v63 state delivery: `9C3D512ACFF549ACBF82A0A46A59D64C6F0F06AD26C831F0DAB7F10A793ED885`
- K2 v64 linked-client picking state: `570BFB5A9AE90AAACDAEBEBCCA2BE0572DC631D7211AC889226A4DF7359CF043`
- K2 v65 authoritative linked-client broadcasts: `82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB`
- cgame v61: `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`

`python -m thorgor patches install --hon-home PATH` preserves verified stock
and linked-delivery backups and installs only complete outputs matching the
catalog hashes. The first K2 builder accepts either verified stock input above,
normalizes the retired auto-patcher URL to localhost, and produces the redirect
baseline. The linked-delivery builder walks every linked client while retaining
the established queue filters. The final recipient fix is declarative. Unknown
versions without a verified backup are rejected.

The builders can also be invoked directly:

```text
python -m thorgor patches apply client.server_redirects INPUT_K2_DLL OUTPUT_K2_DLL
python -m thorgor patches apply dedicated.state_delivery_linked INPUT_K2_BASELINE_DLL OUTPUT_K2_DLL
python -m thorgor patches apply dedicated.hero_state_recipient_fix INPUT_LINKED_K2_DLL OUTPUT_K2_DLL
python -m thorgor patches apply dedicated.complete_registry_guard INPUT_CGAME_DLL OUTPUT_CGAME_DLL
```

Generated DLLs, backups, candidates, and original game files are excluded by `.gitignore` and must never be committed.
