# Print decoded instructions from a starting address.
# Usage: DumpListing.py address count
# @category ThorGor
address = toAddr(getScriptArgs()[0])
count = int(getScriptArgs()[1])
instruction = getInstructionAt(address)
if instruction is None:
    instruction = getInstructionContaining(address)
for index in range(count):
    if instruction is None:
        break
    print("%s  %s" % (instruction.getAddress(), instruction.toString()))
    instruction = instruction.getNext()
