async def read_vlq(stream):
    """
    Reads a VLQ from a stream, and returns both the parsed value and the bytes belonging to it.
    :param stream: A stream object, with readexactly() defined.
    :return: int, bytes: The parsed value and unparsed value of the VLQ.
    """
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
    """
    Much like read_vlq, but accounts for signedness.
    :param stream: A stream object, with readexactly() defined.
    :return: int, bytes: The parsed value and unparsed value of the VLQ.
    """
    value, raw_bytes = await read_vlq(stream)
    if (value & 1) == 0x00:
        return value >> 1, raw_bytes
    else:
        return -((value >> 1) + 1), raw_bytes
