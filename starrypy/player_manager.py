from datetime import datetime
import logging
import pprint
import re

import sqlalchemy as sqla
from sqlalchemy.orm import relationship

from .decorators import EventHook
from .enums import ConnectionState, PacketType, BanType
from .packet import Packet
from .storage_manager import cache_query, DeclarativeBase, db_session


class Ban(DeclarativeBase):
    __tablename__ = "bans"

    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    ip = sqla.Column(sqla.String(39))
    uuid = sqla.Column(sqla.String(32))
    reason = sqla.Column(sqla.String(255))
    banned_by = sqla.Column(sqla.String(24))
    banned_at = sqla.Column(sqla.DateTime)
    ban_type = sqla.Column(sqla.Enum(BanType))
    duration = sqla.Column(sqla.String(10))

    def __repr__(self):
        return f"<Ban(uuid={self.uuid}, ip={self.ip}, reason={self.reason}, by={self.banned_by}," \
               f" type={self.ban_type}, when={self.banned_at}, duration={self.duration}>"


class IP(DeclarativeBase):
    __tablename__ = "ips"

    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    ip = sqla.Column(sqla.String(39))
    uuid = sqla.Column(sqla.String(32), sqla.ForeignKey("players.uuid"))
    last_seen = sqla.Column(sqla.DateTime)

    player = relationship("Player", back_populates="ips")

    def __repr__(self):
        return "<IP(ip={}, uuid={})>".format(self.ip, self.uuid)


class Player(DeclarativeBase):
    __tablename__ = "players"

    uuid = sqla.Column(sqla.String(32), primary_key=True)
    original_name = sqla.Column(sqla.String(255))
    name = sqla.Column(sqla.String(255))
    alias = sqla.Column(sqla.String(24))
    species = sqla.Column(sqla.String(16))

    location = sqla.Column(sqla.String(255))

    first_seen = sqla.Column(sqla.DateTime)
    last_seen = sqla.Column(sqla.DateTime)

    logged_in = sqla.Column(sqla.Boolean)
    client_id = sqla.Column(sqla.Integer)
    current_ip = sqla.Column(sqla.String(39))

    def __repr__(self):
        return f"<Player(name={self.name}, uuid={self.uuid}, logged_in={self.logged_in})>"

    def __str__(self):
        return pprint.pformat(self.__dict__)


Player.ips = relationship("IP", order_by=IP.id, back_populates="player")


class PlayerManager:
    name = "player_manager"

    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.player_manager")
        self.logger.debug("Initializing Player manager framework.")
        self.factory = factory
        self.config_manager = factory.config_manager
        self._clean_slate()

    # Connect Sequence
    @EventHook(PacketType.PROTOCOL_REQUEST)
    async def connection_step_1(self, packet, client):
        """
        A client opens a channel with the server, and announces it's version
        number.

        If, for what ever reason, we wanted to track clients version numbers,
        we'd do that here. No reason to at this time, however.
        """

        # self.logger.debug("C -> S: Protocol Request")
        client.connection_state = ConnectionState.CLIENT_VERSION_SENT
        return True

    @EventHook(PacketType.PROTOCOL_RESPONSE)
    async def connection_step_2(self, packet, client):
        """
        The server responds with a simple True or False regarding if the
        version the client is attempting to connect with, is allowed.
        """

        # self.logger.debug("C <- S: Protocol response")
        client.connection_state = ConnectionState.VERSION_OK_WITH_SERVER
        return True

    @EventHook(PacketType.CLIENT_CONNECT)
    async def connection_step_3(self, packet, client):
        """
        The client, upon getting an Version OK from the server, announces its
        intention to connect, by sending over a bunch of data. This is our
        first big data-scrape.

        Big things we can get: Name, Species, UUID, Name used for login, ship
        fuel, ship level, ship crew size, fuel efficiency, ship speed, and
        ship capabilities.

        Othere things we can get: ship chunks, and asset digest, and the
        allow asset mismatch option.
        """

        # self.logger.debug("C -> S: Client Connect")
        client.connection_state = ConnectionState.CLIENT_CONNECT

        player = await self._add_or_get_player(**packet.parsed_data, ip=client.ip_address)
        client.player = player

        banned = await self._check_bans(client)

        # TODO: Check for valid species

        species_rejected = await self._check_species(client)

        return not (banned or species_rejected)

    @EventHook(PacketType.HANDSHAKE_CHALLENGE)
    async def connection_step_3a(self, packet, client):
        """
        When servers implement a password authentication system, this packet
        is sent back to the clients.
        """

        # self.logger.debug("C <- S: Handshake Challenge")
        client.connection_state = ConnectionState.HANDSHAKE_CHALLENGE
        return True

    @EventHook(PacketType.HANDSHAKE_RESPONSE)
    async def connection_step_3b(self, packet, client):
        """
        The client's hashed password based on the server-provided salt, gets
        sent back.
        """

        # self.logger.debug("C -> S: Handshake Response")
        client.connection_state = ConnectionState.HANDSHAKE_CHALLENGE_RESPONSE
        return True

    @EventHook(PacketType.CONNECT_SUCCESS)
    async def connection_step_4(self, packet, client):
        """
        Provided all the previous steps completed successfully, the server
        gives the client the thumbs-up to connect here. More data-scraping
        here.

        Big things we get: Player's partial stellar position on server. We
        only get the planet and satellite number here.

        Other things: Client id for this session, server UUID, chunk size,
        coordinate ranges for X,Y, and Z.
        """

        # self.logger.debug("C <- S: Connect Success")
        client.connection_state = ConnectionState.CONNECTED
        try:
            with db_session() as db:
                client.player.logged_in = True
                client.player.last_seen = datetime.now()
                client.player.client_id = packet.parsed_data['client_id']
                db.commit()
            self.logger.info(f"{client.player.alias} [client id: {client.player.client_id}] has logged in.")
        except Exception as e:
            self.logger.debug(f"Failed to update player info: {e}")
        return True

    @EventHook(PacketType.CONNECT_FAILURE)
    async def connection_step_4a(self, packet, client):
        """
        In the event that the client does not provide the server with
        permissible values (bad asset hash, bad username, bad password, etc.
        the server will respond with a string, and this packet will cause
        the client to disconnect.

        Modifying this packet is useful for sending clients additional
        disconnect reasons (eg - when a player is banned from the server)
        """

        # self.logger.debug("C <- S: Connect Failure")
        client.connection_state = ConnectionState.DISCONNECTED
        return True

    # @EventHook(PacketType.STEP_UPDATE)
    # async def connection_step_5(self, packet, client):
    #     """
    #     Heartbeat detected¸ we are fully connected
    #     """
    #
    #     # TODO: Test performance impact of having this.
    #     # Note- this packet is ever changing, so caching it is a
    #     # BAD idea.
    #
    #     # self.logger.debug("C <- S: Connect Failure")
    #     if client.connection_state != ConnectionState.CONNECTED_WITH_HEARTBEAT:
    #         client.connection_state = ConnectionState.CONNECTED_WITH_HEARTBEAT
    #     return True

    # Disconnecting
    @EventHook(PacketType.CLIENT_DISCONNECT_REQUEST)
    async def disconnect_a(self, packet, client):
        """
        Sent when a client is doing an orderly shutdown. This is an empty
        packet, and is only really used to serve as a trigger for the server
        to initiate the disconnect.
        """

        # self.logger.debug("C -> S: Client Disconnect Request")
        client.connection_state = ConnectionState.CLIENT_DISCONNECTING
        return True

    @EventHook(PacketType.SERVER_DISCONNECT)
    async def disconnect_b(self, packet, client):
        """
        Similar to the Connection Failure packet, this packet is sent by the
        server to tell the client it is disconnected. In practice, the
        response is left blank when everything is shutdown correctly.

        Useful for telling the client it has been kicked or banned.
        """

        # self.logger.debug("C <- S: Server Disconnect")
        client.connection_state = ConnectionState.DISCONNECTED
        self.logger.info(f"{client.player.alias} [client id: {client.player.client_id}] has disconnected.")
        await self.close_out(client)
        return True

    # Connected and working
    @EventHook(PacketType.WORLD_START, priority=1)
    async def player_arrives(self, packet, client):
        planet_template = packet.parsed_data["template_data"]["celestialParameters"]
        if planet_template is not None:
            coord = planet_template["coordinate"]
            planet_str = f"CelestialWorld:{coord['location'][0]}:{coord['location'][1]}:{coord['location'][2]}" \
                         f":{coord['planet']}"
            if coord["satellite"] > 0:
                planet_str += ":{coord['satellite']}"
            self.logger.debug(planet_str)
            with db_session() as db:
                client.player.location = planet_str
                db.commit()
        return True

    async def _add_or_get_player(self, player_uuid=None, player_name=None, player_species=None, ip=None, **kwargs):
        """
        Check if a player is in the database; if they aren't, add them. If
        they are, get their record. In either case, cache their record for
        future use.
        """

        # Convert to more friendly formats
        if isinstance(player_uuid, bytes):
            player_uuid = player_uuid.decode("ascii")
        if isinstance(player_name, bytes):
            player_name = player_name.decode("utf-8")

        # Generate the player alias. Fail back to a chunk of their UUID
        alias = self._clean_name(player_name)
        if alias is None:
            self.logger.warning("No valid characters used in player name - falling back to UUID.")
            alias = player_uuid[:4]

        # Track the IP address that was used to connect
        with db_session() as db:
            ip_address = db.query(IP).filter_by(ip=ip, uuid=player_uuid).first()
            if not ip_address:
                ip_address = IP(ip=ip, uuid=player_uuid, last_seen=datetime.now())
                db.add(ip_address)
            else:
                ip_address.last_seen = datetime.now()
            db.commit()

        # Grab the player entry from the database. If it doesn't exist, create it.
        player = None
        with db_session() as db:
            player = db.query(Player).filter_by(uuid=player_uuid).first()
            if player:
                self.logger.debug(f"Known player attempting login: {alias} ({player_uuid})")
                if player.logged_in:
                    raise ValueError("Player is already logged in.")
                if player.name != player_name:
                    player.name = player_name
                player.alias = alias
                player.current_ip = ip
            else:
                self.logger.info(f"A new player is connecting: {alias} ({player_uuid})")

                same_alias = db.query(Player).filter_by(alias=alias).first()
                while same_alias:
                    self.logger.warning(f"User with alias {alias} already exists! Trying {alias}_...")
                    alias += "_"
                    same_alias = db.query(Player).filter_by(alias=alias).first()

                player = Player(uuid=player_uuid,
                                original_name=player_name,
                                name=player_name,
                                alias=alias,
                                species=player_species,
                                first_seen=datetime.now(),
                                last_seen=datetime.now(),
                                logged_in=False,
                                current_ip=ip)
                db.add(player)
            db.commit()

        # Return the player object
        return cache_query(player)

    @staticmethod
    def _clean_name(name):
        """
        Remove all the unwanted stuff from a users name, to turn it into
        something more easy to type in the chat box.
        """

        # strips any strings like ^colour; and any non-ascii characters (probably)
        char_strip = re.compile(r"\^[^\s]*?;|[^ -~]+")

        # strips any leading or trailing whitespace, and all excess whitespace over one character long
        whitespace_strip = re.compile(r"(?<=\s)\s+|^\s+|\s+$")

        alias = whitespace_strip.sub("", char_strip.sub("", name))

        # No names over 24 characters please and thank you
        return alias[:24] if alias else None

    async def close_out(self, client):
        """
        Make sure the player entry in the database gets properly updated on
        disconnect.
        """

        try:
            with db_session() as db:
                client.player.logged_in = False
                client.player.last_seen = datetime.now()
                client.player.client_id = -1
                db.commit()
        except Exception as e:
            self.logger.debug(f"Failed to update player info: {e}")

    def _clean_slate(self):
        """
        Sever has freshly started. Make sure that all users in the database
        are marked as logged out.
        """

        try:
            with db_session() as db:
                players = db.query(Player).filter_by(logged_in=True).all()
                for player in players:
                    self.logger.warning(f"Correcting logged_in state on {player.alias}.")
                    player.logged_in = False
                    player.client_id = -1
                db.commit()
        except Exception as e:
            self.logger.debug(f"Failed to update database: {e}")

    async def _check_species(self, client):
        species = client.player.species
        if species not in self.config_manager.config["player_manager"]["allowed_species"]:
            message = f"^red;Your characters species \"{species}\" is not allowed on this server!"
            await self.write_rejection(client, message)
            return True
        return False

    async def _check_bans(self, client):
        with db_session() as db:
            ip_ban = db.query(Ban).filter_by(ip=client.ip_address, ban_type=BanType.IP).first()
            uuid_ban = db.query(Ban).filter_by(uuid=client.player.uuid, ban_type=BanType.UUID).first()

            reason = None
            if ip_ban:
                self.logger.info(f"IP Banned user attempted to login.")
                reason = ip_ban.reason
            if uuid_ban:
                self.logger.info(f"UUID Banned user attempted to login.")
                reason = uuid_ban.reason

            if reason is not None:
                message = f"^red;You are banned!^reset;\nReason: {reason}"
                await self.write_rejection(client, message)
                return True
            return False

    @staticmethod
    async def write_rejection(client, msg):
        """
        A convenience function for writing a connection failure to a connecting client.

        :param client: The Client to write the packet to.
        :param msg: The message to send with the rejection.
        :return: None
        """
        reject_packet = await Packet.from_parsed(PacketType.CONNECT_FAILURE, {"reason": msg})
        await client.write_to_client(reject_packet)