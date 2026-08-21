# Milestone v70: safe manager rollback

The v69 experiment appended `allheroes:true` to the native manager `0x26`
start-game command. A 3.2.7.1 client dump captured immediately after lobby
creation showed an invalid indirect jump to `0x00000500`, with the first
return addresses inside `game_shared.dll`. The manager log confirmed that the
only new input immediately before the fault was the injected option.

v70 removes that injection and restores the previously tested manager bridge
binary. The stable v65 K2 and v61 cgame patches remain unchanged, including
the player-name synchronization fix. Hero availability for joined players is
still unresolved and must be addressed without altering this native option
string.

Restored `ThorGorManagerBridge.exe` SHA-256:

`ABF0334688C1BEE10DFBA14F83C33751B0B0C80CBE6842261840DA71450A4B92`
