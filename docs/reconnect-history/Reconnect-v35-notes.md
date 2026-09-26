# Reconnect v35 — isolated creator-departure host migration

V35 keeps the live-confirmed v32 reconnect and control path unchanged.

The v34 live test generated `crash_3.2.7.1_0035.dmp` when player2 disconnected,
before reconnect began. The dump places the caller at game.dll RVA `0x32E81`.
Ghidra shows that ordinary disconnection jumps directly to RVA `0x32FB2`; v34's
five-byte inline patch had overwritten the first byte of that stock target.

V35 removes the unsafe inline rewrite. It detours at RVA `0x32FA3` to an isolated
24-byte cave at RVA `0x73D90`, performs the host-successor hit/miss decision, and
returns to the original stock destinations. RVA `0x32FB2` remains exactly
`8B90E8000000` and has a native execution regression test.

Verified outputs:

- game.dll: `0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B`
- k2.dll: `BA14F2931FF6F5FB9377FAECECA2F3A96A53436D61CD7984D002A5F24616B35C`

Live acceptance test:

1. Start a fresh two-player match.
2. Disconnect player2 and verify the slave remains alive.
3. Reconnect player2 and verify immediate control of the correct hero.
4. Disconnect creator `player` and verify player2 remains in the match.
5. Reconnect creator and verify the original hero and controls.

Install locally with `INSTALL_RECONNECT_V35.bat`. No GitHub push is part of this
iteration.
