# Security and privacy

ThorGor is an experimental LAN service. Do not expose it directly to the public Internet.

## Sensitive runtime material

The following files can contain credentials, usernames, LAN addresses, session proofs, cookies, authentication hashes, or packet data:

- `thorgor_accounts.db`
- `*.log` and `dashboard_logs/`
- `work/` and runtime state files
- capture directories and debug/session ZIPs
- crash dumps

These paths are ignored by Git. Do not override the ignore rules or force-add them. Before sharing any diagnostic bundle, inspect and redact it outside the repository.

The two milestone login pairs and the dedicated-manager password embedded in the launchers are intentionally public compatibility defaults for an isolated LAN experiment. They must never be reused for a real account or an Internet-facing service.

## Reporting

Do not open a public issue containing a database, password, session value, packet capture, crash dump, private address, or unredacted log. Describe the symptom first and arrange a private transfer if detailed evidence is genuinely required.

## Patch safety

The patch builders accept only exact HoN 3.2.7.1 input hashes and verify exact output hashes. Do not weaken these checks to support an unknown binary.
