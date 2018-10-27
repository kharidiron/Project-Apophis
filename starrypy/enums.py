from enum import Enum, IntEnum, auto


class PacketType(IntEnum):
    # Connection protocol handshake
    PROTOCOL_REQUEST = 0
    PROTOCOL_RESPONSE = auto()
    # Universe; server -> client
    SERVER_DISCONNECT = auto()
    CONNECT_SUCCESS = auto()
    CONNECT_FAILURE = auto()
    HANDSHAKE_CHALLENGE = auto()
    CHAT_RECEIVED = auto()
    UNIVERSE_TIME_UPDATE = auto()
    CELESTIAL_RESPONSE = auto()
    PLAYER_WARP_RESULT = auto()
    PLANET_TYPE_UPDATE = auto()
    PAUSE = auto()
    SERVER_INFO = auto()
    # Universe; client -> server
    CLIENT_CONNECT = auto()
    CLIENT_DISCONNECT_REQUEST = auto()
    HANDSHAKE_RESPONSE = auto()
    PLAYER_WARP = auto()
    FLY_SHIP = auto()
    CHAT_SENT = auto()
    CELESTIAL_REQUEST = auto()
    # Universe; client <--> server
    CLIENT_CONTEXT_UPDATE = auto()
    # World; server -> client
    WORLD_START = auto()
    WORLD_STOP = auto()
    WORLD_LAYOUT_UPDATE = auto()
    WORLD_PARAMETERS_UPDATE = auto()
    CENTRAL_STRUCTURE_UPDATE = auto()
    TILE_ARRAY_UPDATE = auto()
    TILE_UPDATE = auto()
    TILE_LIQUID_UPDATE = auto()
    TILE_DAMAGE_UPDATE = auto()
    TILE_MODIFICATION_FAILURE = auto()
    GIVE_ITEM = auto()
    ENVIRONMENT_UPDATE = auto()
    UPDATE_TILE_PROTECTION = auto()
    SET_DUNGEON_GRAVITY = auto()
    SET_DUNGEON_BREATHABLE = auto()
    SET_PLAYER_START = auto()
    FIND_UNIQUE_ENTITY_RESPONSE = auto()
    PONG = auto()
    # World; client -> server
    MODIFY_TILE_LIST = auto()
    DAMAGE_TILE_GROUP = auto()
    COLLECT_LIQUID = auto()
    REQUEST_DROP = auto()
    SPAWN_ENTITY = auto()
    CONNECT_WIRE = auto()
    DISCONNECT_ALL_WIRES = auto()
    WORLD_CLIENT_STATE_UPDATE = auto()
    FIND_UNIQUE_ENTITY = auto()
    WORLD_START_ACKNOWLEDGE = auto()
    PING = auto()
    # World; client <--> server
    ENTITY_CREATE = auto()
    ENTITY_UPDATE = auto()
    ENTITY_DESTROY = auto()
    ENTITY_INTERACT = auto()
    ENTITY_INTERACT_RESULT = auto()
    HIT_REQUEST = auto()
    DAMAGE_REQUEST = auto()
    DAMAGE_NOTIFICATION = auto()
    ENTITY_MESSAGE = auto()
    ENTITY_MESSAGE_RESPONSE = auto()
    UPDATE_WORLD_PROPERTIES = auto()
    STEP_UPDATE = auto()
    # System; server -> client
    SYSTEM_WORLD_START = auto()
    SYSTEM_WORLD_UPDATE = auto()
    SYSTEM_OBJECT_CREATE = auto()
    SYSTEM_OBJECT_DESTROY = auto()
    SYSTEM_SHIP_CREATE = auto()
    SYSTEM_SHIP_DESTROY = auto()
    # System; client -> server
    SYSTEM_OBJECT_SPAWN = auto()


class PacketDirection(Enum):
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


class BanType(Enum):
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
