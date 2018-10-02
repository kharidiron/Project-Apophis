import io
import logging
import struct
import zlib
from asyncio import sleep
from binascii import hexlify, unhexlify
from typing import BinaryIO, Callable, List, Dict, Any, Union, Hashable, Optional

from .enums import PacketType, PacketDirection, WarpType, WarpWorldType, SystemLocationType


_cache = {}
parser_logger = logging.getLogger("starrypy.parser")

JsonType = Union[None, bool, int, float, str, List["JsonType"], Dict[str, "JsonType"]]

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
    "vec2ui": struct.Struct(">2L"),
    "vec3i": struct.Struct(">3l")
}

# Basic data type parsing


def parse_byte(stream: BinaryIO) -> int:
    return ord(stream.read(1))


def build_byte(obj: int) -> bytes:
    return obj.to_bytes(1, byteorder="big", signed=False)


def parse_with_struct(stream: BinaryIO, data_type: str) -> Union[bool, int, float, tuple]:
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


def build_with_struct(obj: Union[bool, int, float, tuple], data_type: str) -> bytes:
    """
    This function takes a variety of simple input data types and turns them into bytes depending on data_type.
    :param obj: The object to be parsed. Should be one of [bool, int, float] or a tuple of int or float.
    :param data_type: str, the struct type to use. Valid values are listed in struct_cache.
    :return: bytes: The packed form of the input data.
    """
    return struct_cache[data_type].pack(obj)


def parse_vlq(stream: BinaryIO) -> int:
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


def build_vlq(obj: int) -> bytes:
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


def parse_signed_vlq(stream: BinaryIO) -> int:
    v = parse_vlq(stream)
    if (v & 1) == 0x00:
        return v >> 1
    else:
        return -((v >> 1) + 1)


def build_signed_vlq(obj: int) -> bytes:
    value = abs(obj * 2)
    if obj < 0:
        value -= 1
    return build_vlq(value)


def parse_byte_array(stream: BinaryIO) -> bytes:
    array_len = parse_vlq(stream)
    return stream.read(array_len)


def build_byte_array(obj: bytes) -> bytes:
    return build_vlq(len(obj)) + obj


def parse_utf8_string(stream: BinaryIO) -> str:
    return parse_byte_array(stream).decode("utf-8")


def build_utf8_string(obj: str) -> bytes:
    return build_byte_array(obj.encode("utf-8"))


def parse_string_set(stream: BinaryIO) -> List[str]:
    set_len = parse_vlq(stream)
    return [parse_utf8_string(stream) for _ in range(set_len)]


def build_string_set(obj: List[str]) -> bytes:
    res = b''
    res += build_vlq(len(obj))
    return res + b"".join(x.encode("utf-8") for x in obj)


def parse_uuid(stream: BinaryIO) -> bytes:
    return hexlify(stream.read(16))


def build_uuid(obj: bytes) -> bytes:
    return unhexlify(obj)


def parse_json(stream: BinaryIO) -> JsonType:
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


def build_json(obj: JsonType) -> bytes:
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


def parse_json_array(stream: BinaryIO) -> List[JsonType]:
    return parse_set(stream, parse_json)


def build_json_array(obj: List[JsonType]) -> bytes:
    return build_set(obj, build_json)


def parse_json_object(stream: BinaryIO) -> Dict[str, JsonType]:
    return parse_hashmap(stream, parse_utf8_string, parse_json)


def build_json_object(obj: Dict[str, JsonType]) -> bytes:
    return build_hashmap(obj, build_utf8_string, build_json)

# Higher-level data object parsing functions


def parse_maybe(stream: BinaryIO,
                data_type: Callable[[BinaryIO], Any]) -> Optional:
    if parse_with_struct(stream, "bool"):
        return data_type(stream)
    return None


def build_maybe(obj: Optional, data_type: Callable[[Any], bytes]) -> bytes:
    if obj is not None:
        return build_with_struct(True, "bool") + data_type(obj)
    return build_with_struct(False, "bool")


def parse_set(stream: BinaryIO, data_type: Callable[[BinaryIO], Any]) -> List:
    set_len = parse_vlq(stream)
    return [data_type(stream) for _ in range(set_len)]


def build_set(obj: List, data_type: Callable[[Any], bytes]) -> bytes:
    res = build_vlq(len(obj))
    return res + b"".join(data_type(x) for x in obj)


def parse_hashmap(stream: BinaryIO, key_type: Callable[[BinaryIO], Hashable],
                  value_type: Callable[[BinaryIO], Any]) -> Dict:
    map_len = parse_vlq(stream)
    return dict((key_type(stream), value_type(stream)) for _ in range(map_len))


def build_hashmap(obj: Dict, key_type: Callable[[Hashable], bytes],
                  value_type: Callable[[Any], bytes]) -> bytes:
    res = build_vlq(len(obj))
    key_list = (key_type(x) for x in obj.keys())
    val_list = (value_type(x) for x in obj.values())
    return res + b"".join(j for i in zip(key_list,val_list) for j in i)


def parse_chat_header(stream: BinaryIO) -> Dict:
    res = {"mode": parse_byte(stream)}
    if res["mode"] > 1:
        res["channel"] = parse_utf8_string(stream)
    else:
        res["channel"] = ""
        res["unknown"] = parse_byte(stream)  # Spooky
    res["client_id"] = parse_with_struct(stream, "uint16")
    return res


def build_chat_header(obj: Dict) -> bytes:
    res = build_byte(obj["mode"])
    if obj["mode"] > 1:
        res += build_utf8_string(obj["channel"])
    else:
        res += build_byte(obj["unknown"])
    res += build_with_struct(obj["client_id"], "uint16")
    return res


def parse_celestial_coordinates(stream: BinaryIO) -> Dict:
    return {
        "coordinates": parse_with_struct(stream, "vec3i"),
        "planet": parse_with_struct(stream, "int32"),
        "satellite": parse_with_struct(stream, "int32")
    }


def build_celestial_coordinates(obj: Dict) -> bytes:
    return b"".join((build_with_struct(obj["coordinates"], "vec3i"),
                     build_with_struct(obj["planet"], "int32"),
                     build_with_struct(obj["satellite"], "int32")))


def parse_system_location(stream: BinaryIO) -> Dict:
    dest_type = parse_byte(stream)
    res = {"type": dest_type}
    if dest_type == SystemLocationType.SYSTEM:
        pass
    elif dest_type == SystemLocationType.COORDINATE:
        res["coordinates"] = parse_celestial_coordinates(stream)
    elif dest_type == SystemLocationType.ORBIT:
        res["coordinates"] = parse_celestial_coordinates(stream)
        res["direction"] = parse_with_struct(stream, "int32")
        res["enter_time"] = parse_with_struct(stream, "double")
        res["enter_position"] = parse_with_struct(stream, "vec2f")
    elif dest_type == SystemLocationType.UUID:
        res["destination_id"] = parse_uuid(stream)
    elif dest_type == SystemLocationType.LOCATION:
        res["location"] = parse_with_struct(stream, "vec2f")
    else:
        raise TypeError(f"System location type {dest_type} is not defined for parsing!")
    return res


def build_system_location(obj: Dict) -> bytes:
    dest_type = obj["type"]
    res = build_byte(dest_type)
    if dest_type == SystemLocationType.SYSTEM:
        pass
    elif dest_type == SystemLocationType.COORDINATE:
        res += build_celestial_coordinates(obj["coordinates"])
    elif dest_type == SystemLocationType.ORBIT:
        orbit_li = (
            build_celestial_coordinates(obj["coordinates"]),
            build_with_struct(obj["direction"], "int32"),
            build_with_struct(obj["enter_time"], "double"),
            build_with_struct(obj["enter_position"], "vec2f")
        )
        res += b"".join(orbit_li)
    elif dest_type == SystemLocationType.UUID:
        res += build_uuid(obj["destination_id"])
    elif dest_type == SystemLocationType.LOCATION:
        res += build_with_struct(obj["location"], "vec2f")
    else:
        raise TypeError(f"System location type {dest_type} is not defined for parsing!")
    return res


def parse_warp_action(stream: BinaryIO) -> Dict:
    warp_type = parse_byte(stream)
    res = {"warp_type": warp_type}

    if warp_type == WarpType.TO_WORLD:
        world_type = parse_byte(stream)
        res["world_type"] = world_type
        if world_type == WarpWorldType.CELESTIAL_WORLD:
            res["celestial_coordinates"] = parse_celestial_coordinates(stream)
            res["teleporter"] = parse_maybe(stream, parse_utf8_string)
        elif world_type == WarpWorldType.SHIP_WORLD:
            res["ship_owner"] = parse_uuid(stream)
            res["start_position"] = parse_maybe(stream, lambda x: parse_with_struct(x, "vec2ui"))
        elif world_type == WarpWorldType.UNIQUE_WORLD:
            res["world_name"] = parse_utf8_string(stream)
            res["instance_id"] = parse_maybe(stream, parse_uuid)
            res["level"] = parse_maybe(stream, lambda x: parse_with_struct(x, "float"))
            res["teleporter_id"] = parse_maybe(stream, parse_utf8_string)
        else:
            raise TypeError(f"World warp type {world_type} is not defined for parsing!")

    elif warp_type == WarpType.TO_PLAYER:
        res["player_id"] = parse_uuid(stream)

    elif warp_type == WarpType.TO_ALIAS:
        res["alias_type"] = parse_with_struct(stream, "int32")

    else:
        raise TypeError(f"Warp type {warp_type} is not defined for parsing!")

    return res


def build_warp_action(obj: Dict) -> bytes:
    warp_type = obj["warp_type"]
    res = build_byte(warp_type)

    if warp_type == WarpType.TO_WORLD:
        world_type = obj["world_type"]
        res += build_byte(world_type)
        if world_type == WarpWorldType.CELESTIAL_WORLD:
            res += build_celestial_coordinates(obj["celestial_coordinates"])
            res += build_maybe(obj["teleporter"], build_utf8_string)
        elif world_type == WarpWorldType.SHIP_WORLD:
            res += build_uuid(obj["ship_owner"])
            res += build_maybe(obj["start_position"], lambda x: build_with_struct(x, "vec2ui"))
        elif world_type == WarpWorldType.UNIQUE_WORLD:
            data_li = (
                build_utf8_string(obj["world_name"]),
                build_maybe(obj["instance_id"], build_uuid),
                build_maybe(obj["level"], lambda x: build_with_struct(x, "float")),
                build_maybe(obj["teleporter_id"], build_utf8_string)
            )
            res += b"".join(data_li)
        else:
            raise TypeError(f"World warp type {world_type} is not defined for parsing!")

    elif warp_type == WarpType.TO_PLAYER:
        res += build_uuid(obj["player_id"])

    elif warp_type == WarpType.TO_ALIAS:
        res += build_with_struct(obj["alias_type"], "int32")

    else:
        raise TypeError(f"Warp type {warp_type} is not defined for parsing!")

    return res


def parse_world_chunks(stream: BinaryIO) -> Dict:
    # I'll be honest, I've not a damned clue what's going on in this thing.
    # And honestly, it's doubtful we'll need any more parsing than this;
    # Python is simply too slow for us to be parsing tile arrays and such
    array_len = parse_vlq(stream)
    chunks = [(i, parse_byte_array(stream), parse_byte(stream), parse_byte_array(stream))
              for i in range(array_len)]
    return {"length": array_len, "contents": chunks}


def parse_client_context_set(stream: BinaryIO, direction: PacketDirection) -> Dict[str, JsonType]:
    res = {"_length": parse_vlq(stream)}
    parser_logger.debug(f"Length: {res['_length']}")
    if direction == PacketDirection.TO_CLIENT:
        res["_sub_length"] = parse_vlq(stream)
        parser_logger.debug(f"Sublength: {res['_sub_length']}")
        if res["_sub_length"] == 0:  # Dunno what it is? Screw it! The information we really want isn't here anyways.
            res["_unknown"] = stream.read()
        else:
            res["rpcs"] = parse_json_array(stream)
    else:
        res["rpcs"] = parse_json_array(stream)
    return res


def build_client_context_set(obj: Dict, direction: PacketDirection) -> bytes:
    if direction != PacketDirection.TO_SERVER:  # We only support building to-server CCUs; they do what we need.
        raise NotImplementedError("CCS to client building not implemented yet.")
    res = build_json_array(obj["rpcs"])
    res = build_vlq(len(res)) + res
    return res

# Specific packet parsing functions
# These receive two arguments from parse_ or build_packet
# Arg 1 is either the data stream or the parsed_data dict from the packet, depending on if reading or writing
# Arg 2 is the direction the packet is going in, as a PacketDirection
# Most packets don't need the second one, but it's there when they do

# Protocol packets
# - Protocol request


def parse_protocol_request(stream: BinaryIO, _) -> Dict:
    return {"request_protocol_version": parse_with_struct(stream, "uint32")}

# - Protocol response


def parse_protocol_response(stream: BinaryIO, _) -> Dict:
    return {"allowed": parse_with_struct(stream, "bool")}

# Universe server to client
# - Server disconnect


def parse_server_disconnect(stream: BinaryIO, _) -> Dict:
    return {"reason": parse_utf8_string(stream)}


def build_server_disconnect(obj: Dict, _) -> bytes:
    return build_utf8_string(obj["reason"])

# - Connect success


def parse_connect_success(stream: BinaryIO, _) -> Dict:
    return {
        "client_id": parse_vlq(stream),
        "server_uuid": parse_uuid(stream),
        "planet_orbital_levels": parse_with_struct(stream, "int32"),
        "satellite_orbital_levels": parse_with_struct(stream, "int32"),
        "chunk_size": parse_with_struct(stream, "int32"),
        "xy_coord_range": parse_with_struct(stream, "vec2i"),
        "z_coord_range": parse_with_struct(stream, "vec2i")
    }


def build_connect_success(obj: Dict, _) -> bytes:
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


def parse_connect_failure(stream: BinaryIO, _) -> Dict:
    return {"reason": parse_utf8_string(stream)}


def build_connect_failure(obj: Dict, _) -> bytes:
    return build_utf8_string(obj["reason"])

# - Handshake challenge


def parse_handshake_challenge(stream: BinaryIO, _) -> Dict:
    return {"password_salt": parse_byte_array(stream)}

# - Chat received


def parse_chat_received(stream: BinaryIO, _) -> Dict:
    return {
        "header": parse_chat_header(stream),
        "name": parse_utf8_string(stream),
        "junk": parse_byte(stream),
        "message": parse_utf8_string(stream)
    }


def build_chat_received(obj: Dict, _) -> bytes:
    res = build_chat_header(obj["header"])
    res += build_utf8_string(obj["name"])
    res += build_byte(obj["junk"])
    res += build_utf8_string(obj["message"])
    return res

# - Universe time update


def parse_universe_time_update(stream: BinaryIO, _) -> Dict:
    return {"timestamp": parse_with_struct(stream, "double")}


def build_universe_time_update(obj: Dict, _) -> bytes:
    return build_with_struct(obj["timestamp"], "double")

# - Player warp result


def parse_player_warp_result(stream: BinaryIO, _) -> Dict:
    return {
        "success": parse_with_struct(stream, "bool"),
        "warp_action": parse_warp_action(stream),
        "warp_action_invalid": parse_with_struct(stream, "bool")
    }


def build_player_warp_result(obj: Dict, _) -> bytes:
    res = build_with_struct(obj["success"], "bool")
    res += build_warp_action(obj["warp_action"])
    return res + build_with_struct(obj["warp_action_invalid"], "bool")

# Universe client to server
# - Client connect


def parse_client_connect(stream: BinaryIO, _) -> Dict:
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


def parse_handshake_response(stream: BinaryIO, _) -> Dict:
    return {"password_hash": parse_byte_array(stream)}

# - Player warp-


def parse_player_warp(stream: BinaryIO, _) -> Dict:
    return {
        "warp_action": parse_warp_action(stream),
        "deploy": parse_with_struct(stream, "bool")
    }


def build_player_warp(obj: Dict, _) -> bytes:
    return build_warp_action(obj["warp_action"]) + build_with_struct(obj["deploy"], "bool")

# - Fly ship


def parse_fly_ship(stream: BinaryIO, _) -> Dict:
    return {
        "system": parse_with_struct(stream, "vec3i"),
        "location": parse_system_location(stream)
    }


def build_fly_ship(obj: Dict, _) -> bytes:
    return build_with_struct(obj["system"], "vec3i") + build_system_location(obj["location"])

# - Chat send


def parse_chat_send(stream: BinaryIO, _) -> Dict:
    return {
        "text": parse_utf8_string(stream),
        "send_mode": parse_byte(stream)
    }


def build_chat_send(obj: Dict, _) -> bytes:
    return build_utf8_string(obj["text"]) + build_byte(obj["send_mode"])

# World server to client
# - World Start


def parse_world_start(stream: BinaryIO, _) -> Dict:
    return {
        "template_data": parse_json(stream),
        "sky_data": parse_byte_array(stream),
        "weather_data": parse_byte_array(stream),
        "player_start": parse_with_struct(stream, "vec2f"),
        "player_respawn": parse_with_struct(stream, "vec2f"),
        "respawn_in_world": parse_with_struct(stream, "bool"),
        "world_properties": parse_json(stream),
        "dungeon_id_gravity": parse_hashmap(stream, lambda x: parse_with_struct(x, "uint16"),
                                            lambda x: parse_with_struct(x, "float")),
        "dungeon_id_breathable": parse_hashmap(stream, lambda x: parse_with_struct(x, "uint16"),
                                               lambda x: parse_with_struct(x, "bool")),
        "protected_dungeon_ids": parse_set(stream, lambda x: parse_with_struct(x, "uint16")),
        "client_id": parse_with_struct(stream, "uint16"),
        "local_interpolation_mode": parse_with_struct(stream, "bool")
    }

# - Give item


def parse_give_item(stream: BinaryIO, _) -> Dict:
    return {
        "name": parse_utf8_string(stream),
        "count": parse_vlq(stream),
        "parameters": parse_json(stream)
    }


def build_give_item(obj: Dict, _) -> bytes:
    return build_utf8_string(obj["name"]) + build_vlq(obj["count"]) + build_json(obj["parameters"])

# World bidirectional
# - Step update


def parse_step_update(stream: BinaryIO, _) -> Dict:
    # The documents lie! This is a VLQ, not a Unsigned int 64.
    return {"remote_step": parse_vlq(stream)}

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
    PacketType.CHAT_RECEIVED: (parse_chat_received, build_chat_received),
    PacketType.UNIVERSE_TIME_UPDATE: (parse_universe_time_update, build_universe_time_update),
    PacketType.PLAYER_WARP_RESULT: (parse_player_warp_result, build_player_warp_result),
    PacketType.FLY_SHIP: (parse_fly_ship, build_fly_ship),
    PacketType.CHAT_SENT: (parse_chat_send, build_chat_send),
    PacketType.CLIENT_CONNECT: (parse_client_connect, None),
    PacketType.HANDSHAKE_RESPONSE: (parse_handshake_response, None),
    PacketType.PLAYER_WARP: (parse_player_warp, build_player_warp),
    PacketType.CLIENT_CONTEXT_UPDATE: (parse_client_context_set, build_client_context_set),
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
        packet_hash = hash(packet)
        if packet_hash in _cache:
            packet.parsed_data = _cache[packet_hash].get()
            return packet
        try:
            data_stream = io.BytesIO(packet.data)
            packet.parsed_data = parse_funcs[0](data_stream, packet.direction)
            _cache[packet_hash] = CachedPacket(packet.parsed_data)
            leftover_data = data_stream.read()
            if leftover_data:
                parser_logger.debug(f"Packet parsing for type {PacketType(packet.type)} has leftover data! Data:\n"
                                    f"{hexlify(leftover_data)}")
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
        except TypeError:
            raise NotImplementedError
        return packet


async def reap_packets(reap_time):
    # noinspection PyBroadException
    try:
        while True:
            await sleep(reap_time)
            for p_hash, packet in _cache.copy().items():
                if packet.reap_check():
                    del _cache[p_hash]
    except Exception:
        parser_logger.exception("Exception occurred while reaping packets.", exc_info=True)


class CachedPacket:

    def __init__(self, parsed_data):
        self._count = 1
        self._parsed_data = parsed_data

    def get(self):
        self._count += 1
        return self._parsed_data.copy()

    def reap_check(self):
        self._count -= 1
        return self._count <= 0
