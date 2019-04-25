import logging

import sqlalchemy as sqla
from sqlalchemy.orm import relationship

from .decorators import EventHook
from .enums import PacketType, WarpWorldType, WarpType, WarpAliasType
from .storage_manager import DeclarativeBase, db_session
from .player_manager import Player


class World(DeclarativeBase):
    __tablename__ = "worlds"

    location_str = sqla.Column(sqla.String(255), primary_key=True)
    type = sqla.Column(sqla.Enum(WarpWorldType))

    __mapper_args__ = {
        "polymorphic_identity": WarpWorldType.NONE,
        "polymorphic_on": type
    }


class Planet(World):
    x = sqla.Column(sqla.Integer)
    y = sqla.Column(sqla.Integer)
    z = sqla.Column(sqla.Integer)
    planet = sqla.Column(sqla.Integer)
    satellite = sqla.Column(sqla.Integer)
    name = sqla.Column(sqla.String(255))

    __mapper_args__ = {
        "polymorphic_identity": WarpWorldType.CELESTIAL_WORLD
    }


class Ship(World):
    owner_id = sqla.Column(sqla.String(32), sqla.ForeignKey("players.uuid"))
    owner = relationship("Player", foreign_keys=owner_id)

    __mapper_args__ = {
        "polymorphic_identity": WarpWorldType.SHIP_WORLD
    }


class Instance(World):
    instance_type = sqla.Column(sqla.String(255))
    instance_id = sqla.Column(sqla.String(32))

    __mapper_args__ = {
        "polymorphic_identity": WarpWorldType.UNIQUE_WORLD
    }


class WorldManager:
    name = "world_manager"

    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.world_manager")
        self.logger.debug("Initializing world manager framework.")
        self.factory = factory
        self.config_manager = factory.config_manager

    @EventHook(PacketType.WORLD_START, priority=99)
    async def _get_celestial_world(self, packet, client):
        c_params = packet.parsed_data["template_data"]["celestialParameters"]
        if c_params:
            client.player.location = self._add_or_get_planet(c_params)
            self.logger.info(f"Player {client.player.alias} is now on {client.player.location.location_str}.")
        return True

    @EventHook(PacketType.PLAYER_WARP_RESULT, priority=99)
    async def _get_other_world(self, packet, client):
        if packet.parsed_data["success"]:
            warp_data = packet.parsed_data["warp_action"]
            p = client.player
            last_loc = p.location
            with db_session() as db:
                if warp_data["warp_type"] == WarpType.TO_ALIAS:
                    if warp_data["alias_type"] == WarpAliasType.SHIP:
                        p.location = db.query(Ship).filter_by(owner_id=p.uuid).first()
                    elif warp_data["alias_type"] == WarpAliasType.ORBITED:
                        # We have to get info from world_start in this case.
                        pass
                    elif warp_data["alias_type"] == WarpAliasType.RETURN:
                        # Swap current and last location.
                        p.location, p.previous_location = p.previous_location, p.location
                        db.commit()
                        return True
                elif warp_data["warp_type"] == WarpType.TO_PLAYER:
                    player_warped_to = db.query(Player).filter_by(uuid=warp_data["player_uuid"].decode('utf-8')).first()
                    p.location = player_warped_to.location
                elif warp_data["warp_type"] == WarpType.TO_WORLD:
                    if warp_data["world_type"] == WarpWorldType.CELESTIAL_WORLD:
                        # This gets dealt with in the WORLD_START hook.
                        pass
                    elif warp_data["world_type"] == WarpWorldType.SHIP_WORLD:
                        p.location = self._add_or_get_ship(warp_data["ship_owner"].decode('utf-8'))
                    elif warp_data["world_type"] == WarpWorldType.UNIQUE_WORLD:
                        if warp_data.get("instance_id"):  # Only persistent instances have IDs.
                            p.location = self._add_or_get_instance(warp_data["instance_type"],
                                                                   warp_data["instance_id"].decode('utf-8'))
                p.previous_location = last_loc
                db.commit()
        return True

    def _add_or_get_planet(self, c_params):
        coords = c_params["coordinate"]
        planet_str = "CelestialWorld:{0}:{1}:{2}:{planet}".format(*coords["location"], planet=coords["planet"])
        if coords["satellite"] > 0:
            planet_str += f":{coords['satellite']}"
        with db_session() as db:
            planet = db.query(Planet).filter_by(location_str=planet_str).first()
            if planet:
                return planet
            else:
                self.logger.info(f"Adding entry for new planet {planet_str}.")
                new_planet = Planet(location_str=planet_str, x=coords["location"][0], y=coords["location"][1],
                                    z=coords["location"][2], planet=coords["planet"], satellite=coords["satellite"],
                                    name=c_params["name"])
                db.add(new_planet)
                db.commit()
                return new_planet

    def _add_or_get_ship(self, owner_uuid):
        loc_str = f"ShipWorld:{owner_uuid}"
        with db_session() as db:
            owner = db.query(Player).filter_by(uuid=owner_uuid).first()
            ship = db.query(Ship).filter_by(location_str=loc_str).first()
            if ship:
                return ship
            else:
                self.logger.info(f"Adding entry for new ship belonging to {owner.alias}.")
                new_ship = Ship(location_str=loc_str, owner=owner)
                db.add(new_ship)
                db.commit()
                return new_ship

    def _add_or_get_instance(self, instance_type, instance_id):
        loc_str = f"InstanceWorld:{instance_type}:{instance_id}"
        with db_session() as db:
            instance = db.query(Instance).filter_by(location_str=loc_str).first()
            if instance:
                return instance
            else:
                self.logger.info(f"Adding entry for new persistent instance {loc_str}.")
                new_instance = Instance(location_str=loc_str, instance_type=instance_type, instance_id=instance_id)
                db.add(new_instance)
                db.commit()
                return new_instance
