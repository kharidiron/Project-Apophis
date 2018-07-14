import asyncio
import zlib
from .spy_utils import read_vlq_signed

zobj = zlib.decompressobj()


async def read_packet(stream, direction):
    """
    Given an interface to read from (reader) read the next packet that comes
    in. Determine the packet's type, decode its contents, and track the
    direction it is flowing. Store this all in a packet object, and return it
    for further processing down the line.
    :param stream: Stream from which to read the packet.
    :param direction: Destination for the packet (SERVER or CLIENT).
    :return: Dictionary. Contains both raw and decoded versions of the packet.
    """
    p = {}
    compressed = False

    packet_type = await stream.readexactly(1)
    packet_size, packet_size_data = await read_vlq_signed(stream)
    if packet_size < 0:
        packet_size = abs(packet_size)
        compressed = True

    data = await stream.readexactly(packet_size)
    p['type'] = ord(packet_type)
    p['size'] = packet_size
    p['compressed'] = compressed
    if not compressed:
        p['data'] = data
    else:
        try:
            p['data'] = zobj.decompress(data)
        except zlib.error:
            raise asyncio.IncompleteReadError

    p['original_data'] = packet_type + packet_size_data + data
    p['direction'] = direction

    return p