# Reconnect development history

These documents preserve observations from superseded reconnect experiments.
They are diagnostic history, not active installation instructions.

The old numbered launchers were removed because they did not embed their named
binary version. Each wrapper applied whichever patch manifest was currently
checked out, so using an old filename could silently install the newest build.
Use Git commits and milestone tags to reproduce old code and use the active
root installer for the current build.

Current frozen recovery point:

- Commit `f8bd799`
- Tag `reconnect-v39-both-accounts-reconnect-milestone`
- Active launcher `INSTALL_RECONNECT_V39.bat`

Historical references to removed installers inside these notes are retained as
part of the original test record and should not be followed from the current
checkout.
