from enum import IntEnum, unique


@unique  # Just to avoid potential developer errors
class PacketType(IntEnum):
    # Handshake packets
    PROTOCOL_REQUEST = 0
    PROTOCOL_RESPONSE = 1
    # Universe; server → client
    SERVER_DISCONNECT = 2
    CONNECT_SUCCESS = 3
    CONNECT_FAILURE = 4
    HANDSHAKE_CHALLENGE = 5
    CHAT_RECEIVED = 6
    UNIVERSE_TIME_UPDATE = 7
    CELESTIAL_RESPONSE = 8
    PLAYER_WARP_RESULT = 9
    PLANET_TYPE_UPDATE = 10
    PAUSE = 11
    # Universe; client → server
    CLIENT_CONNECT = 12
    CLIENT_DISCONNECT_REQUEST = 13
    HANDSHAKE_RESPONSE = 14
    PLAYER_WARP = 15
    FLY_SHIP = 16
    CHAT_SENT = 17
    CELESTIAL_REQUEST = 18
    # Universe; bidirectional
    CLIENT_CONTEXT_UPDATE = 19
    # World; server → client
    WORLD_START = 20
    WORLD_STOP = 21
    WORLD_LAYOUT_UPDATE = 22
    WORLD_PARAMETERS_UPDATE = 23
    CENTRAL_STRUCTURE_UPDATE = 24
    TILE_ARRAY_UPDATE = 25
    TILE_UPDATE = 26
    TILE_LIQUID_UPDATE = 27
    TILE_DAMAGE_UPDATE = 28
    TILE_MODIFICATION_FAILURE = 29
    GIVE_ITEM = 30
    ENVIRONMENT_UPDATE = 31
    UPDATE_TILE_PROTECTION = 32
    SET_DUNGEON_GRAVITY = 33
    SET_DUNGEON_BREATHABLE = 34
    SET_PLAYER_START = 35
    FIND_UNIQUE_ENTITY_RESPONSE = 36
    # World; client → server
    MODIFY_TILE_LIST = 37
    DAMAGE_TILE_GROUP = 38
    COLLECT_LIQUID = 39
    REQUEST_DROP = 40
    SPAWN_ENTITY = 41
    CONNECT_WIRE = 42
    DISCONNECT_ALL_WIRES = 43
    WORLD_CLIENT_STATE_UPDATE = 44
    FIND_UNIQUE_ENTITY = 45
    UNKNOWN = 46  # Gonna need to figure this one out some time
    # World; bidirectional
    ENTITY_CREATE = 47
    ENTITY_UPDATE = 48
    ENTITY_DESTROY = 49
    ENTITY_INTERACT = 50
    ENTITY_INTERACT_RESULT = 51
    HIT_REQUEST = 52
    DAMAGE_REQUEST = 53
    DAMAGE_NOTIFICATION = 54
    ENTITY_MESSAGE = 55
    ENTITY_MESSAGE_RESPONSE = 56
    UPDATE_WORLD_PROPERTIES = 57
    STEP_UPDATE = 58
    # System; server → client
    SYSTEM_WORLD_START = 59
    SYSTEM_WORLD_UPDATE = 60
    SYSTEM_OBJECT_CREATE = 61
    SYSTEM_OBJECT_DESTROY = 62
    SYSTEM_SHIP_CREATE = 63
    SYSTEM_SHIP_DESTROY = 64
    # System; client → server
    SYSTEM_OBJECT_SPAWN = 65


class PacketDirection(IntEnum):
    TO_CLIENT = 0
    TO_SERVER = 1
    FROM_CLIENT = 1
    FROM_SERVER = 0


class SystemLocationType(IntEnum):
    SYSTEM = 0
    COORDINATE = 1
    ORBIT = 2
    UUID = 3
    LOCATION = 4


class WarpType(IntEnum):
    TO_WORLD = 1
    TO_PLAYER = 2
    TO_ALIAS = 3


class WarpWorldType(IntEnum):
    CELESTIAL_WORLD = 1
    SHIP_WORLD = 2
    UNIQUE_WORLD = 3


class WarpAliasType(IntEnum):
    RETURN = 0
    ORBITED = 1
    SHIP = 2
