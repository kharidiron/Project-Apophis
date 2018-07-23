from datetime import datetime
import logging
import pprint
import re

import sqlalchemy as sqla
from sqlalchemy.orm import relationship

from .decorators import EventHook
from .enums import PacketType, ConnectionState
from .storage_manager import DeclarativeBase, db_session


class Player(DeclarativeBase):
    __tablename__ = "players"

    uuid = sqla.Column(sqla.String(32), primary_key=True)
    original_name = sqla.Column(sqla.String(255))
    name = sqla.Column(sqla.String(255))
    alias = sqla.Column(sqla.String(24))
    species = sqla.Column(sqla.String(16))

    first_seen = sqla.Column(sqla.DateTime)
    last_seen = sqla.Column(sqla.DateTime)

    logged_in = sqla.Column(sqla.Boolean)
    client_id = sqla.Column(sqla.Integer)
    current_ip = sqla.Column(sqla.String(15))

    def __repr__(self):
        return f"<Player(name={self.name}, uuid={self.uuid}, logged_in={self.logged_in})>"

    def __str__(self):
        return pprint.pformat(self.__dict__)


class PlayerManager:
    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.player_manager")
        self.logger.debug("Initializing Player manager framework.")
        self.factory = factory
        self.config_manager = factory.config_manager

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
        The client, upon getting an OK from the server, announces its
        intention to connect, by sending over a bunch of data. This is our
        first big data-scrape.

        Big things we can get: Name, Species, UUID, Name used for login, ship
        fuel, ship level, ship crew size, fuel efficiency, ship speed, and
        ship capabilities.

        The less useful values are the ship chunks, and asset digest, and the
        allow asset mismatch option.
        """

        # self.logger.debug("C -> S: Client Connect")
        client.connection_state = ConnectionState.CLIENT_CONNECT

        player = await self._add_or_get_player(**packet.parsed_data, ip=client.ip_address)

        return True

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
        return True

    async def _add_or_get_player(self, player_uuid=None, player_name=None, player_species=None, ip=None, **kwargs):
        # Convert to more friendly formats
        if isinstance(player_uuid, bytes):
            player_uuid = player_uuid.decode("ascii")
        if isinstance(player_name, bytes):
            player_name = player_name.decode("utf-8")

        # Generate the player alias. Fail back to a chunk of their UUID
        alias = self._clean_name(player_name)
        if alias is None:
            self.logger.warning("No valid characters used in player name - falling back to UUID.")
            alias = player_uuid[0:4]

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

                # TODO: Check for alias already in use

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
        return player

    @staticmethod
    def _clean_name(name):
        """
        Remove all the unwanted stuff from a users name, to turn it into
        something more easy to type in the chat box.

        :param name:
        :return:
        """

        # strips any strings like ^colour; and any non-ascii characters (probably)
        char_strip = re.compile(r"\^[^\s]*?;|[^ -~]+")

        # strips any leading or trailing whitespace, and all excess whitespace over one character long
        whitespace_strip = re.compile(r"(?<=\s)\s+|^\s+|\s+$")

        alias = whitespace_strip.sub("", char_strip.sub("", name))

        # No names over 24 characters please and thank you
        return alias[:24] if alias else None
