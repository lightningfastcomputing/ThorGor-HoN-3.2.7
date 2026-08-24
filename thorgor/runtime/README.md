# Portable runtime payload

This directory contains the frozen, verified v77 service implementations and
the minimum PowerShell/patch assets needed by `../START_STACK.bat`.

The stable modules outside this directory are the public API. They load these
files only through `thorgor.compat` while behavior is migrated subsystem by
subsystem. The synchronization regression test requires bundled files to stay
byte-identical to their repository-root source counterparts.

Runtime databases, logs, captures, and dashboard output are created here and
remain excluded from version control.
