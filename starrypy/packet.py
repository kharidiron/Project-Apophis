import asyncio
import zlib
from .enums import PacketType, PacketDirection
from .parser import parse_packet, build_packet
from .spy_utils import read_vlq_signed


class Packet:
    def __init__(self, packet_type: int, data: bytes, direction: int,
                 size: int=None, compressed=False, original_data: bytes=None, parsed_data: dict=None):
        self.type = packet_type
        self.size = size
        self.compressed = compressed
        self.data = data
        self.original_data = original_data
        self.direction = direction
        if parsed_data is None:
            self.parsed_data = {}
        else:
            self.parsed_data = parsed_data
        self.edited_data = {}
        self.parse = lambda: parse_packet(self)
        self.build = lambda: build_packet(self)

    @classmethod
    async def from_parsed(cls, packet_type: int, parsed_data: dict, direction: int=0):
        """
        Takes in parsed packet data (for example, as built by a plugin) and returns a fully-built packet,
        ready for sending.
        :param packet_type: A PacketType value indicating the type of packet to build.
        :param parsed_data: A dictionary containing parsed data appropriate to the packet.
        :param direction: A PacketDirection indicating which way the packet should be going. Optional on
        non-bidirectional packets.
        :return: A fully-built Packet object.
        """
        return await cls(packet_type, b"", direction, parsed_data=parsed_data).build()

    def copy(self):
        return Packet(self.type, self.data, self.direction, size=self.size, compressed=self.compressed,
                      original_data=self.original_data, parsed_data=self.parsed_data)

    async def build_edits(self):
        if self.edited_data:
            self.parsed_data.update(self.edited_data)
            await self.build()

    def __repr__(self):
        return f"<Packet type={PacketType(self.type)} direction={PacketDirection(self.direction)}>"

    def __hash__(self):
        return hash(self.original_data)


async def read_packet(stream, direction):
    """
    Given an interface to read from (reader) read the next packet that comes
    in. Determine the packet's type, decode its contents, and track the
    direction it is flowing. Store this all in a packet object, and return it
    for further processing down the line.
    :param stream: Stream from which to read the packet.
    :param direction: Destination for the packet (SERVER or CLIENT).
    :return: Packet: Contains both raw and decoded versions of the packet.
    """
    compressed = False

    packet_type = await stream.readexactly(1)
    packet_size, packet_size_data = await read_vlq_signed(stream)
    if packet_size < 0:
        packet_size = abs(packet_size)
        compressed = True

    data = await stream.readexactly(packet_size)
    p_type_int = ord(packet_type)

    if compressed:
        try:
            final_data = zlib.decompress(data)
        except zlib.error:
            raise asyncio.IncompleteReadError
    else:
        final_data = data
    original_data = packet_type + packet_size_data + data

    return Packet(p_type_int, final_data, direction,
                  size=packet_size_data, compressed=compressed, original_data=original_data)
