import logging

import sqlalchemy as sqla
from sqlalchemy.orm import relationship

from .enums import PacketType
from .decorators import EventHook
from .storage_manager import DeclarativeBase


class Player(DeclarativeBase):
    __tablename__ = "players"

    uuid = sqla.Column(sqla.String(32), primary_key=True)
    name = sqla.Column(sqla.String(255))

    def __str__(self):
        self.logger.info(f"{self.__dict__}")


class PlayerManager:
    def __init__(self, factory):
        self.factory = factory
        self.config_manager = factory.config_manager
        self.logger = logging.getLogger("starrypy.player_manager")
        self.logger.debug("Initialized Player manager framework.")

    # Connect Sequence
    @EventHook(PacketType.PROTOCOL_REQUEST, priority=10)
    def connection_step_1(self, packet, client):
        self.logger.debug("PReq")
        return True

    @EventHook(PacketType.PROTOCOL_RESPONSE, priority=10)
    def connection_step_2(self, packet, client):
        self.logger.debug("PResp")
        return True

    @EventHook(PacketType.CLIENT_CONNECT, priority=10)
    def connection_step_3(self, packet, client):
        self.logger.debug("CConn")
        return True

    @EventHook(PacketType.HANDSHAKE_CHALLENGE, priority=10)
    def connection_step_3a(self, packet, client):
        self.logger.debug("HC")
        return True

    @EventHook(PacketType.HANDSHAKE_RESPONSE, priority=10)
    def connection_step_3b(self, packet, client):
        self.logger.debug("HR")
        return True

    @EventHook(PacketType.CONNECT_SUCCESS, priority=10)
    def connection_step_4(self, packet, client):
        self.logger.debug("CS")
        return True

    @EventHook(PacketType.CONNECT_FAILURE, priority=10)
    def connection_step_4a(self, packet, client):
        self.logger.debug("CF")
        return True

    # Disconnecting
    @EventHook(PacketType.CLIENT_DISCONNECT_REQUEST)
    def disconnect_a(self, packet, client):
        return True

    @EventHook(PacketType.SERVER_DISCONNECT)
    def disconnect_b(self, packet, client):
        return True
