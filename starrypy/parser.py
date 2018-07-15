import io
import struct
import zlib
from binascii import hexlify, unhexlify

from .enums import PacketType
# from .packet import Packet


# Some structs, pre-built for performance

struct_cache = {
    "bool": struct.Struct(">?"),
    "uint16": struct.Struct(">H"),
    "int16": struct.Struct(">h"),
    "uint32": struct.Struct(">L"),
    "int32": struct.Struct(">l"),
    "uint64": struct.Struct(">Q"),
    "int64": struct.Struct(">q"),
    "float": struct.Struct(">f"),
    "double": struct.Struct(">d"),
    "vec2f": struct.Struct(">2f"),
    "vec2i": struct.Struct(">2l"),
    "vec3i": struct.Struct(">3l")
}

# Basic data type parsing


def parse_byte(stream):
    return ord(stream.read(1))


def build_byte(obj):
    return obj.to_bytes(1, byteorder="big", signed=False)


def parse_with_struct(stream: io.BytesIO, data_type: str):
    """
    This function takes an input stream and transforms it into a variety of data types, depending on data_type.
    :param stream: A stream object of raw bytes.
    :param data_type: str, the struct type to use. Valid values are listed in struct_cache.
    :return: The unpacked value.
    """
    s = struct_cache[data_type]
    unpacked = s.unpack(stream.read(s.size))
    if len(unpacked) == 1:  # Don't return a tuple if there's only one element
        unpacked = unpacked[0]
    return unpacked


def build_with_struct(obj, data_type: str):
    """
    This function takes a variety of simple input data types and turns them into bytes depending on data_type.
    :param obj: The object to be parsed. Should be one of [bool, int, float] or a tuple of int or float.
    :param data_type: str, the struct type to use. Valid values are listed in struct_cache.
    :return: bytes: The packed form of the input data.
    """
    return struct_cache[data_type].pack(obj)


def parse_vlq(stream: io.BytesIO):
    value = 0
    while True:
        try:
            tmp = ord(stream.read(1))
            value = (value << 7) | (tmp & 0x7f)
            if tmp & 0x80 == 0:
                break
        except TypeError:
            break
    return value


def build_vlq(obj: int):
    result = bytearray()
    value = int(obj)
    if obj == 0:
        result = bytearray(b'\x00')
    else:
        while value > 0:
            byte = value & 0x7f
            value >>= 7
            if value != 0:
                byte |= 0x80
            result.insert(0, byte)
        if len(result) > 1:
            result[0] |= 0x80
            result[-1] ^= 0x80
    return bytes(result)


def parse_signed_vlq(stream: io.BytesIO):
    v = parse_vlq(stream)
    if (v & 1) == 0x00:
        return v >> 1
    else:
        return -((v >> 1) + 1)


def build_signed_vlq(obj: int):
    value = abs(obj * 2)
    if obj < 0:
        value -= 1
    return build_vlq(value)


def parse_byte_array(stream: io.BytesIO):
    array_len = parse_vlq(stream)
    return stream.read(array_len)


def build_byte_array(obj: bytes):
    return build_vlq(len(obj)) + obj


def parse_utf8_string(stream: io.BytesIO):
    return parse_byte_array(stream).decode("utf-8")


def build_utf8_string(obj: str):
    return build_byte_array(obj.encode("utf-8"))


def parse_string_set(stream: io.BytesIO):
    set_len = parse_vlq(stream)
    return [parse_utf8_string(stream) for _ in range(set_len)]


def build_string_set(obj: list):
    res = b''
    res += build_vlq(len(obj))
    return res + b"".join(x.encode("utf-8") for x in obj)


def parse_uuid(stream: io.BytesIO):
    return hexlify(stream.read(16))


def build_uuid(obj: bytes):
    return unhexlify(obj)


def parse_json(stream: io.BytesIO):
    t = parse_byte(stream)
    if t == 1:
        # null
        return None
    elif t == 2:
        # floating-point
        return parse_with_struct(stream, "double")
    elif t == 3:
        # boolean
        return parse_with_struct(stream, "bool")
    elif t == 4:
        # integer
        return parse_signed_vlq(stream)
    elif t == 5:
        # string
        return parse_utf8_string(stream)
    elif t == 6:
        # array
        return parse_json_array(stream)
    elif t == 7:
        # object (map or dictionary)
        return parse_json_object(stream)
    else:
        raise ValueError(f"Json does not have type with index {t}!")


def build_json(obj):
    res = b""
    if obj is None:
        res += b"\x01"
    elif isinstance(obj, float):
        res += b"\x02" + build_with_struct(obj, "double")
    elif isinstance(obj, bool):
        res += b"\x03" + build_with_struct(obj, "bool")
    elif isinstance(obj, int):
        res += b"\x04" + build_signed_vlq(obj)
    elif isinstance(obj, str):
        res += b"\x05" + build_utf8_string(obj)
    elif isinstance(obj, list):
        res += b"\x06" + build_json_array(obj)
    elif isinstance(obj, dict):
        res += b"\x07" + build_json_object(obj)
    else:
        raise TypeError(f"Object with type {type(obj)} is not a valid JSON object!")
    return res


def parse_json_array(stream: io.BytesIO):
    array_len = parse_vlq(stream)
    return [parse_json(stream) for _ in range(array_len)]


def build_json_array(obj: list):
    res = build_vlq(len(obj))
    res += b"".join(build_json(x) for x in obj)
    return res


def parse_json_object(stream: io.BytesIO):
    obj_len = parse_vlq(stream)
    return dict((parse_utf8_string(stream), parse_json(stream)) for _ in range(obj_len))


def build_json_object(obj: dict):
    res = build_vlq(len(obj))
    key_list = (build_utf8_string(x) for x in obj.keys())
    val_list = (build_json(x) for x in obj.values())
    res += b"".join(zip(key_list, val_list))
    return res

# Higher-level data object parsing functions


def parse_set(stream: io.BytesIO, data_type: str):
    set_len = parse_vlq(stream)
    return [parse_with_struct(stream, data_type) for _ in range(set_len)]


def parse_hashmap(stream: io.BytesIO, key_type: str, value_type: str):
    map_len = parse_vlq(stream)
    return dict((parse_with_struct(stream, key_type), parse_with_struct(stream, value_type))
                 for _ in range(map_len))


def parse_chat_header(stream: io.BytesIO):
    res = {"mode": parse_byte(stream)}
    if res["mode"] > 1:
        res["channel"] = parse_utf8_string(stream)
        res["client_id"] = parse_with_struct(stream, "uint16")
    else:
        res["channel"] = ""
        res["unknown"] = parse_byte(stream)  # Spooky
        res["client_id"] = parse_with_struct(stream, "uint16")
    return res


def parse_world_chunks(stream: io.BytesIO):
    # I'll be honest, I've not a damned clue what's going on in this thing.
    array_len = parse_vlq(stream)
    chunks = [(i, parse_byte_array(stream), parse_byte(stream), parse_byte_array(stream))
              for i in range(array_len)]
    return {"length": array_len, "contents": chunks}

# Specific packet parsing functions
# These receive two arguments from parse_ or build_packet
# Arg 1 is either the data stream or the parsed_data dict from the packet, depending on if reading or writing
# Arg 2 is the direction the packet is going in, as a PacketDirection
# Most packets don't need the second one, but it's there when they do

# Protocol packets
# - Protocol request


def parse_protocol_request(stream: io.BytesIO, _):
    return {"request_protocol_version": parse_with_struct(stream, "uint32")}

# - Protocol response


def parse_protocol_response(stream: io.BytesIO, _):
    return {"allowed": parse_with_struct(stream, "bool")}

# Universe server to client
# - Server disconnect


def parse_server_disconnect(stream: io.BytesIO, _):
    return {"reason": parse_utf8_string(stream)}


def build_server_disconnect(obj: dict, _):
    return build_utf8_string(obj["reason"])

# - Connect success


def parse_connect_success(stream: io.BytesIO, _):
    return {
        "client_id": parse_vlq(stream),
        "server_uuid": parse_uuid(stream),
        "planet_orbital_levels": parse_with_struct(stream, "int32"),
        "satellite_orbital_levels": parse_with_struct(stream, "int32"),
        "chunk_size": parse_with_struct(stream, "int32"),
        "xy_coord_range": parse_with_struct(stream, "vec2i"),
        "z_coord_range": parse_with_struct(stream, "vec2i")
    }


def build_connect_success(obj: dict, _):
    res = [
        build_vlq(obj["client_id"]),
        build_uuid(obj["server_uuid"]),
        build_with_struct(obj["planet_orbital_levels"], "int32"),
        build_with_struct(obj["satellite_orbital_levels"], "int32"),
        build_with_struct(obj["chunk_size"], "int32"),
        build_with_struct(obj["xy_coord_range"], "vec2i"),
        build_with_struct(obj["z_coord_range"], "vec2i")
    ]
    return b"".join(res)

# - Connect failure


def parse_connect_failure(stream: io.BytesIO, _):
    return {"reason": parse_utf8_string(stream)}


def build_connect_failure(obj: dict, _):
    return build_utf8_string(obj["reason"])

# - Handshake challenge


def parse_handshake_challenge(stream: io.BytesIO, _):
    return {"password_salt": parse_byte_array(stream)}

# - Chat received


def parse_chat_received(stream: io.BytesIO, _):
    return {
        "header": parse_chat_header(stream),
        "name": parse_utf8_string(stream),
        "junk": parse_byte(stream),
        "message": parse_utf8_string(stream)
    }

# - Universe time update


def parse_universe_time_update(stream: io.BytesIO, _):
    return {"timestamp": parse_with_struct(stream, "double")}

# Universe client to server
# - Client connect


def parse_client_connect(stream: io.BytesIO, _):
    return {
        "assets_digest": parse_byte_array(stream),
        "allow_assets_mismatch": parse_with_struct(stream, "bool"),
        "player_uuid": parse_uuid(stream),
        "player_name": parse_utf8_string(stream),
        "player_species": parse_utf8_string(stream),
        "ship_chunks": parse_world_chunks(stream),
        "ship_upgrades": {
            "ship_level": parse_with_struct(stream, "uint32"),
            "max_fuel": parse_with_struct(stream, "uint32"),
            "crew_size": parse_with_struct(stream, "uint32"),
            "fuel_efficiency": parse_with_struct(stream, "float"),
            "ship_speed": parse_with_struct(stream, "float"),
            "ship_capabilities": parse_string_set(stream)
        },
        "intro_complete": parse_with_struct(stream, "bool"),
        "account": parse_utf8_string(stream)
    }

# - Handshake response


def parse_handshake_response(stream: io.BytesIO, _):
    return {"password_hash": parse_byte_array(stream)}

# World server to client
# - World Start


def parse_world_start(stream: io.BytesIO, _):
    return {
        "template_data": parse_json(stream),
        "sky_data": parse_byte_array(stream),
        "weather_data": parse_byte_array(stream),
        "player_start": parse_with_struct(stream, "vec2f"),
        "player_respawn": parse_with_struct(stream, "vec2f"),
        "respawn_in_world": parse_with_struct(stream, "bool"),
        "world_properties": parse_json(stream),
        "dungeon_id_gravity": parse_hashmap(stream, "uint16", "float"),
        "dungeon_id_breathable": parse_hashmap(stream, "uint16", "bool"),
        "protected_dungeon_ids": parse_set(stream, "uint16"),
        "client_id": parse_with_struct(stream, "uint16"),
        "local_interpolation_mode": parse_with_struct(stream, "bool")
    }

# World bidirectional
# - Step update


def parse_step_update(stream: io.BytesIO, _):
    return {"remote_step": parse_with_struct(stream, "uint64")}

# Parsing function dispatch thing


parse_map = {
    # Simple format here, key is a PacketType (I personally try to keep this in the order of the Enum)
    # Value is a pair of functions, [0] is for reading, [1] is for writing
    # Slap a None in there if you don't have one of these
    PacketType.PROTOCOL_REQUEST: (parse_protocol_request, None),
    PacketType.PROTOCOL_RESPONSE: (parse_protocol_response, None),
    PacketType.SERVER_DISCONNECT: (parse_server_disconnect, build_server_disconnect),
    PacketType.CONNECT_SUCCESS: (parse_connect_success, build_connect_success),
    PacketType.CONNECT_FAILURE: (parse_connect_failure, build_connect_failure),
    PacketType.HANDSHAKE_CHALLENGE: (parse_handshake_challenge, None),
    PacketType.CHAT_RECEIVED: (parse_chat_received, None),
    PacketType.UNIVERSE_TIME_UPDATE: (parse_universe_time_update, None),
    PacketType.CLIENT_CONNECT: (parse_client_connect, None),
    PacketType.HANDSHAKE_RESPONSE: (parse_handshake_response, None),
    PacketType.WORLD_START: (parse_world_start, None),
    PacketType.STEP_UPDATE: (parse_step_update, None)
}

c_parse_map = {
    # Eventually this is gonna import stuff from the C Parser in the same structure as parse_map
}


try:
    import starrypy.c_parser as cparse
    parse_map.update(c_parse_map)
except ImportError:
    pass


async def parse_packet(packet):
    """
    Takes an input packet, parses it, and returns the packet with the parsed data attached.
    :param packet: A Packet object.
    :return: Packet: The input Packet, but with parsed data added, if applicable.
    """
    parse_funcs = parse_map.get(packet.type, None)
    if parse_funcs is None:
        packet.parsed_data = {}
    else:
        try:
            packet.parsed_data = parse_funcs[0](io.BytesIO(packet.data), packet.direction)
        except IndexError:
            packet.parsed_data = {}
    return packet


async def build_packet(packet):
    """
    Takes an input packet and builds a new raw data string out of the parsed data attached.
    :param packet: A Packet object that's been parsed.
    :return: Packet: The input Packet, with the data, size, and original_data updated to match the parsed data
    """
    parse_funcs = parse_map.get(packet.type, None)
    if parse_funcs is None:
        raise NotImplementedError
    else:
        try:
            packet.data = parse_funcs[1](packet.parsed_data, packet.direction)
            packet.size = len(packet.data)
            if packet.compressed:
                size_bytes = build_signed_vlq(-packet.size)
                data_bytes = zlib.compress(packet.data)
            else:
                size_bytes = build_signed_vlq(packet.size)
                data_bytes = packet.data
            packet.original_data = b"".join((build_byte(packet.type), size_bytes, data_bytes))
        except IndexError:
            raise NotImplementedError
        return packet
