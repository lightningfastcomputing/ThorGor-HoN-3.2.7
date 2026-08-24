# Declarative patch catalog

Every known binary generation now has a named JSON manifest in
`patches/catalog`. A manifest records the exact binary/version, accepted source
hashes, output hash, reason, observed failure, discovery date, and evidence.

List patches with:

```powershell
python -m thorgor patches list
```

Apply a named patch with:

```powershell
python -m thorgor patches apply PATCH_ID SOURCE_DLL OUTPUT_DLL
```

The engine supports declarative file-offset or PE-RVA write operations with
optional original-byte guards. During migration, catalog entries can name an
existing audited builder as an adapter. That status is visible in `patches
list`; it is not considered fully declarative until its manifest contains the
write operations and the adapter is removed.

No patch is applied unless the complete source SHA-256 matches. The complete
result must also match the declared output SHA-256.

