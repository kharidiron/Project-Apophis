import logging

import sqlalchemy as sqla
from sqlalchemy.orm import relationship

from .storage_manager import DeclarativeBase


class Player(DeclarativeBase):
    __tablename__ = "players"

    uuid = sqla.Column(sqla.String(32), primary_key=True)
    name = sqla.Column(sqla.String(255))

    def __str__(self):
        self.logger.info(f"{self.__dict__}")


class PlayerManager:
    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.storage_manager")
        self.factory = factory
