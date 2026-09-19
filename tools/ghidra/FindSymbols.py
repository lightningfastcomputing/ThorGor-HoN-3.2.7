# Print symbols whose names contain any supplied fragment.
# @category ThorGor
patterns = [value.lower() for value in getScriptArgs()]
for symbol in currentProgram.getSymbolTable().getAllSymbols(True):
    name = symbol.getName()
    if any(pattern in name.lower() for pattern in patterns):
        print("%s %s %s" % (symbol.getAddress(), symbol.getSymbolType(), name))
