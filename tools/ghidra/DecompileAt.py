# Decompile the functions containing each supplied address.
# @category ThorGor
from ghidra.app.decompiler import DecompInterface

decompiler = DecompInterface()
decompiler.openProgram(currentProgram)
for raw in getScriptArgs():
    address = toAddr(raw)
    function = getFunctionContaining(address)
    if function is None:
        print("NO_FUNCTION " + raw)
        continue
    print("===== %s %s %s =====" % (raw, function.getName(), function.getEntryPoint()))
    results = decompiler.decompileFunction(function, 120, monitor)
    if not results.decompileCompleted():
        print("DECOMPILE_FAILED " + results.getErrorMessage())
        continue
    print(results.getDecompiledFunction().getC())
decompiler.dispose()
