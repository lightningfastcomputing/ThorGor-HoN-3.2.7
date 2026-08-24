# v77 restored from the frozen working reference — 2026-08-24

The refactored installer temporarily selected the v65 linked-delivery baseline
after a later match-transition test. That rollback reintroduced the established
joined-client gray portrait failure.

The upstream read-only reference at commit `c45b914` identifies v77 as its
frozen working build and installs it on both the host and remote players. The
v77 builder and declarative patch bytes in the refactored tree are byte-identical
to that reference.

ThorGor's supported installer therefore once again advances the verified patch
chain through v65 and installs v77:

`25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026`

The proxy-side packet-copy experiment remains disabled. Hero state is delivered
by K2's original per-recipient serializer, matching the frozen working build.
