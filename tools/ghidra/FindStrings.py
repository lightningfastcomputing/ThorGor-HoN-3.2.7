# Find defined strings containing any supplied fragment and print references.
# Usage: FindStrings.py pattern [pattern...]
# @category ThorGor
patterns = [value.lower() for value in getScriptArgs()]
listing = currentProgram.getListing()
references = currentProgram.getReferenceManager()
for data in listing.getDefinedData(True):
    value = data.getValue()
    if value is None:
        continue
    rendered = str(value)
    if not any(pattern in rendered.lower() for pattern in patterns):
        continue
    print("STRING %s %s" % (data.getAddress(), rendered))
    for reference in references.getReferencesTo(data.getAddress()):
        source = reference.getFromAddress()
        function = getFunctionContaining(source)
        print("  REF %s %s" % (source, function.getName() if function else "<none>"))
