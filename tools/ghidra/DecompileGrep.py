# Print matching portions of one decompiled function.
# Usage: DecompileGrep.py address pattern [pattern...]
# @category ThorGor
from ghidra.app.decompiler import DecompInterface

args = getScriptArgs()
address = toAddr(args[0])
patterns = [value.lower() for value in args[1:]]
function = getFunctionContaining(address)
print("===== %s %s %s =====" % (args[0], function.getName(), function.getEntryPoint()))
decompiler = DecompInterface()
decompiler.openProgram(currentProgram)
results = decompiler.decompileFunction(function, 120, monitor)
lines = results.getDecompiledFunction().getC().splitlines()
selected = set()
for index, line in enumerate(lines):
    if any(pattern in line.lower() for pattern in patterns):
        for selected_index in range(max(0, index - 10), min(len(lines), index + 11)):
            selected.add(selected_index)
last = -2
for index in sorted(selected):
    if index != last + 1:
        print("...")
    print("%04d %s" % (index + 1, lines[index]))
    last = index
decompiler.dispose()
