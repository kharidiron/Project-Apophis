import io
import struct
from binascii import hexlify, unhexlify
from .enums import PacketType

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
    "double": struct.Struct(">d")
}

# Basic data type parsing


def parse_byte(stream):
    return ord(stream.read(1))


def build_byte(obj):
    return obj.to_bytes(1, byteorder="big", signed=False)


def parse_with_struct(stream, data_type):
    s = struct_cache[data_type]
    return s.unpack(stream.read(s.size))[0]


def build_with_struct(obj, type):
    return struct_cache[type].pack(obj)


def parse_vlq(stream):
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


def build_vlq(obj):
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


def parse_signed_vlq(stream):
    v = parse_vlq(stream)
    if (v & 1) == 0x00:
        return v >> 1
    else:
        return -((v >> 1) + 1)


def build_signed_vlq(obj):
    value = abs(obj * 2)
    if obj < 0:
        value -= 1
    return build_vlq(value)


def parse_byte_array(stream):
    l = parse_vlq(stream)
    return stream.read(l)


def build_byte_array(obj):
    return build_vlq(len(obj)) + obj


def parse_utf8_string(stream):
    return parse_byte_array(stream).decode("utf-8")


def build_utf8_string(obj):
    return build_byte_array(obj.encode("utf-8"))


def parse_string_set(stream):
    set_len = parse_vlq(stream)
    return [parse_utf8_string(stream) for _ in range(set_len)]


def build_string_set(obj):
    res = b''
    res += build_vlq(len(obj))
    return res + b"".join(x.encode("utf-8") for x in obj)


def parse_uuid(stream):
    return hexlify(stream.read(16))


def build_uuid(obj):
    return unhexlify(obj)


def parse_json(stream):
    t = parse_byte(stream)
    if t == 1:
        return None
    elif t == 2:
        return parse_with_struct(stream, "double")
    elif t == 3:
        return parse_with_struct(stream, "bool")
    elif t == 4:
        return parse_signed_vlq(stream)
    elif t == 5:
        return parse_utf8_string(stream)
    elif t == 6:
        return parse_json_array(stream)
    elif t == 7:
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



def parse_json_array(stream):
    array_len = parse_vlq(stream)
    return [parse_json(stream) for _ in range(array_len)]


def build_json_array(obj):
    res = build_vlq(len(obj))
    res += b"".join(build_json(x) for x in obj)
    return res


def parse_json_object(stream):
    obj_len = parse_vlq(stream)
    return dict((parse_utf8_string(stream), parse_json(stream)) for _ in range(obj_len))


def build_json_object(obj):
    res = build_vlq(len(obj))
    key_list = (build_utf8_string(x) for x in obj.keys())
    val_list = (build_json(x) for x in obj.values())
    res += b"".join(zip(key_list, val_list))
    return res

# Specific packet parsing functions

def parse_connect_success(stream, _):
    res = {}
    res["client_id"] = parse_vlq(stream)
    res["server_uuid"] = parse_uuid(stream)
    res["planet_orbital_levels"] = parse_with_struct(stream, "int32")
    res["satellite_orbital_levels"] = parse_with_struct(stream, "int32")
    res["chunk_size"] = parse_with_struct(stream, "int32")
    res["xy_min"] = parse_with_struct(stream, "int32")
    res["xy_max"] = parse_with_struct(stream, "int32")
    res["z_min"] = parse_with_struct(stream, "int32")
    res["z_max"] = parse_with_struct(stream, "int32")
    return res


def build_connect_success(obj, _):
    raise NotImplemented


def parse_connect_failure(stream, _):
    return {"reason": parse_utf8_string(stream)}

def build_connect_failure(obj, _):
    return build_utf8_string(obj["reason"])

# Parsing function dispatch thing


parse_map = {
    PacketType.CONNECT_SUCCESS: (parse_connect_success, build_connect_success),
    PacketType.CONNECT_FAILURE: (parse_connect_failure, build_connect_failure)
}

c_parse_map = {

}


try:
    import starrypy.c_parser as cparse
    parse_map.update(c_parse_map)
except ImportError:
    pass


async def parse_packet(packet):
    parse_funcs = parse_map.get(packet["type"], None)
    if parse_funcs is None:
        packet["parsed_data"] = None
    else:
        packet["parsed_data"] = parse_funcs[0](io.BytesIO(packet["data"]), packet["direction"])
    return packet
