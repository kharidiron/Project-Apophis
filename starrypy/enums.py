from enum import IntEnum, unique


@unique  # Just to avoid potential developer errors
class PacketType(IntEnum):
    # Protocol initialization packets
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


class ConnectionState(IntEnum):
    DISCONNECTED = 0
    CLIENT_VERSION_SENT = 1
    VERSION_OK_WITH_SERVER = 2
    CLIENT_CONNECT = 3
    HANDSHAKE_CHALLENGE = 4
    HANDSHAKE_CHALLENGE_RESPONSE = 5
    CONNECT_RESPONSE_SENT = 6
    CONNECTED = 7
    CONNECTED_WITH_HEARTBEAT = 8
    CLIENT_DISCONNECTING = 9


class BanType(IntEnum):
    IP = 1
    UUID = 2


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


class ChatSendMode(IntEnum):
    UNIVERSE = 0
    LOCAL = 1
    PARTY = 2


class ChatReceiveMode(IntEnum):
    LOCAL = 0
    PARTY = 1
    BROADCAST = 2
    WHISPER = 3
    COMMAND_RESULT = 4
    RADIO_MESSAGE = 5
    WORLD = 6


class DamageType(IntEnum):
    NO_DAMAGE = 0  # Assumed
    DAMAGE = 1
    IGNORES_DEF = 2
    KNOCKBACK = 3
    ENVIRONMENT = 4


class DamageHitType(IntEnum):
    NORMAL = 0
    STRONG = 1
    WEAK = 2
    SHIELD = 3
    KILL = 4


class EntityInteractionType(IntEnum):
    NOMINAL = 0
    OPEN_CONTAINER_UI = 1
    GO_PRONE = 2
    OPEN_CRAFTING_UI = 3
    OPEN_NPC_UI = 6
    OPEN_SAIL_UI = 7
    OPEN_TELEPORTER_UI = 8
    OPEN_SCRIPTED_UI = 10
    OPEN_SPECIAL_UI = 11
    OPEN_CREW_UI = 12


class EntitySpawnType(IntEnum):
    PLANT = 0
    OBJECT = 1
    VEHICLE = 2
    ITEM_DROP = 3
    PLANT_DROP = 4
    PROJECTILE = 5
    STAGEHAND = 6
    MONSTER = 7
    NPC = 8
    PLAYER = 9
