# Declarative patch catalog

Named manifests live inside `thorgor/patches/catalog_data`. Patch IDs describe
behavior; historical revisions are stored separately as `legacy_revision`
metadata.

```powershell
python -m thorgor patches list
python -m thorgor patches show dedicated.hero_state_recipient_fix
python -m thorgor patches apply PATCH_ID SOURCE_DLL OUTPUT_DLL
python -m thorgor patches install --hon-home "C:\intelprop\Heroes of Newerth"
```

The engine accepts only complete source hashes declared by a manifest and
verifies the complete output hash. Declarative operations support file offsets
and PE RVAs, original-byte guards, bounds checks, and overlap rejection.

The supported recipient fix is fully declarative. Earlier research generations
retain frozen, hash-verified builders under semantic module names. Their old
revision numbers are diagnostic metadata, not production filenames or product
identity.

Regression tests exercise the clean install chain and backup recovery. The
stable builders have also been compared against verified HoN binaries, yielding:

- linked-delivery K2: `82D0363C...48ECAB`
- recipient-fixed K2: `25B1BB06...CE7026`
- guarded cgame: `88C4ACA3...DF988`
