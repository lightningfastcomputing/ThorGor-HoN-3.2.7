# ThorGor development

- Obtain explicit user approval before any GitHub push. Work locally on a development branch and preserve the frozen v39 commit `f8bd799`. This harness branch starts from the committed reconnect branch tip `dbc7306`.
- Read [the harness guide](docs/TEST_HARNESS.md), [v39 notes](Reconnect-v39-notes.md), [reconnect design](docs/RECONNECT.md), and [lobby authority](docs/LOBBY_AUTHORITY.md) before investigating native regressions. The technical handoff and reconnect history preserve observations from earlier revisions.
- Run `py -m unittest discover -s tests` and the affected scenarios under `py -m thorgor.tools.harness`. Run from the checkout root. The package shim supports checkout names other than `thorgor`.
- Use separate runtime data and disposable accounts. Keep passwords, cookies, raw captures, databases, crash dumps, and game binaries out of source control and shared reports.
- Build binary patches from verified local inputs in a disposable fixture. Keep the builders and expected hashes as the source of truth. Preserve installed and historical binaries, and keep rejected reconnect experiments out of new builds.
- Label evidence as backend protocol, instruction emulation, or live HoN. A successful backend admission establishes creator authority at the master only. Require live evidence for gameplay, UI, and the remaining joiner state freeze.
- The normal dashboard stack owns fixed ports and starts the retail manager. Verify native client profile and network isolation before automating it. Use tracked process ownership and bounded waits for test cleanup.
