# Source-only patching

The repository intentionally distributes patch logic, hashes, and documentation—not game binaries.

## Verified inputs

- Stock HoN 3.2.7.1 `k2.dll`: `8929AE8993AF41AE9F63BEE43DAB27402205621CFFC57F8ACC8DB0C4FB95FAE9`
- Stock HoN 3.2.7.1 `game\cgame.dll`: `45B3CE39214EFD82D12DA8B01E73494CEE983D6DB4891C7D95DF10B2EAA70B02`

## Verified outputs

- K2 v57: `6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF`
- cgame v61: `88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988`

`INSTALL_V61_PATCHES.ps1` preserves verified stock backups and installs only an output matching these hashes. Unknown versions are rejected.

The builders can also be invoked directly:

```text
python patches\build_k2_v57.py INPUT_K2_DLL OUTPUT_K2_DLL
python patches\build_cgame_v61_complete_registry_guard.py INPUT_CGAME_DLL OUTPUT_CGAME_DLL
```

Generated DLLs, backups, candidates, and original game files are excluded by `.gitignore` and must never be committed.
