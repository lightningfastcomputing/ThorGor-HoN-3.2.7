"""Typed PHP wire field extraction for the legacy master responses."""


def parse_php_string_field(wire: bytes, field: str) -> str:
    field_bytes = field.encode('ascii')
    prefix = b's:' + str(len(field_bytes)).encode('ascii') + b':"' + field_bytes + b'";s:'
    offset = wire.find(prefix)
    if offset < 0:
        raise ValueError(f'response has no typed {field} string')
    value_start = offset + len(prefix)
    length_end = wire.find(b':"', value_start)
    if length_end < 0 or not wire[value_start:length_end].isdigit():
        raise ValueError(f'response has invalid {field} string length')
    length = int(wire[value_start:length_end])
    data_start = length_end + 2
    data_end = data_start + length
    if length <= 0 or data_end + 2 > len(wire) or wire[data_end:data_end + 2] != b'";':
        raise ValueError(f'response has invalid {field} string payload')
    return wire[data_start:data_end].decode('utf-8', errors='strict')
