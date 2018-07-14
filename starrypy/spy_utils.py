async def read_vlq(stream):
    raw_bytes = b""
    value = 0
    while True:
        tmp = await stream.readexactly(1)
        raw_bytes += tmp
        tmp = ord(tmp)
        value <<= 7
        value |= tmp & 0x7f

        if tmp & 0x80 == 0:
            break

    return value, raw_bytes


async def read_vlq_signed(stream):
    value, raw_bytes = await read_vlq(stream)
    if (value & 1) == 0x00:
        return value >> 1, raw_bytes
    else:
        return -((value >> 1) + 1), raw_bytes