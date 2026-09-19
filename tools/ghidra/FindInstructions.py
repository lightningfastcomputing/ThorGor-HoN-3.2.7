# Print instructions in an address range containing every supplied text fragment.
# Usage: FindInstructions.py start end fragment [fragment...]
# @category ThorGor
args = getScriptArgs()
start = toAddr(args[0])
end = toAddr(args[1])
patterns = [value.lower() for value in args[2:]]
instruction = getInstructionAt(start)
if instruction is None:
    instruction = getInstructionAfter(start)
while instruction is not None and instruction.getAddress().compareTo(end) < 0:
    rendered = instruction.toString()
    lowered = rendered.lower()
    if all(pattern in lowered for pattern in patterns):
        print("%s  %s" % (instruction.getAddress(), rendered))
    instruction = instruction.getNext()
