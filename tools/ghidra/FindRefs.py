# Print references to each supplied address and the containing function.
# @category ThorGor
for raw in getScriptArgs():
    address = toAddr(raw)
    print("===== REFERENCES TO %s =====" % raw)
    for reference in getReferencesTo(address):
        source = reference.getFromAddress()
        function = getFunctionContaining(source)
        name = function.getName() if function is not None else "<none>"
        entry = function.getEntryPoint() if function is not None else "-"
        print("%s %s %s %s" % (source, reference.getReferenceType(), name, entry))
