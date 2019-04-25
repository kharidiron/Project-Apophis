import asyncio
import logging
from traceback import format_exception

from .enums import PacketDirection
from .enums import PacketDirection, PacketType, ChatReceiveMode
from .plugin_manager import PluginManager
from .packet import read_packet, Packet
from .storage_manager import StorageManager
from .player_manager import PlayerManager
from .world_manager import WorldManager


class ClientSideConnectionFactory:
    clients = []

    def __init__(self, config_manager):
        self.logger = logging.getLogger("starrypy.client_factory")
        self.logger.debug("Initialized client-side connection factory.")
        self.config_manager = config_manager
        self.storage_manager = StorageManager(self)
        self.player_manager = PlayerManager(self)
        self.world_manager = WorldManager(self)
        self.plugin_manager = PluginManager(self)

    def __call__(self, reader, writer):
        self.logger.debug("Establishing new connection.")
        client = Client(reader, writer, self)
        self.clients.append(client)


class Client:
    def __init__(self, reader, writer, factory):
        self.logger = logging.getLogger("starrypy.client_listener")
        self.factory = factory
        self.config_manager = factory.config_manager
        self.storage_manager = factory.storage_manager
        self.player_manager = factory.player_manager
        self.plugin_manager = factory.plugin_manager
        self._alive = True
        self._reader = reader
        self._writer = writer
        self._client_reader = None
        self._client_writer = None
        self.client_loop = None
        self.connection_state = None
        # noinspection PyProtectedMember
        self.ip_address = reader._transport.get_extra_info("peername")[0]
        self.logger.info(f"Connection established from IP {self.ip_address}.")

        self.server_loop = asyncio.create_task(self.server_listener())

    async def server_listener(self):
        """
        Listens for packets going from this client to server.
        """
        conf = self.config_manager.config
        self._client_reader, self._client_writer = await asyncio.open_connection(conf["upstream_host"],
                                                                                 conf["upstream_port"])
        self.client_loop = asyncio.create_task(self.client_listener())
        # noinspection PyBroadException
        try:
            while True:
                packet = await read_packet(self._reader, PacketDirection.TO_SERVER)
                # self.logger.debug(f"  -> S: {packet.type}")
                if await self.plugin_manager.hook_event(packet, self):
                    await self.write_to_server(packet)
        except asyncio.IncompleteReadError as e:
            exception_text = "\n".join(format_exception(*e))
            self.logger.debug(f"Incomplete read occurred. Details:\n{exception_text}")
        except asyncio.CancelledError as e:
            self.logger.warning("Connection ended abruptly.")
            exception_text = "\n".join(format_exception(*e))
            self.logger.debug(f"Connection cancellation details:\n{exception_text}")
        except ConnectionResetError as e:
            self.logger.warning("Connection ended abruptly on the client side.")
            await self.player_manager.close_out(self)
        except Exception:
            self.logger.exception("Exception occurred in server listener.", exc_info=True)
        finally:
            self.logger.debug(f"Closing server listener for IP {self.ip_address}.")
            self.client_loop.cancel()
            self.die()

    async def client_listener(self):
        """
        Listens for packets going from server to this client.
        """
        try:
            while True:
                packet = await read_packet(self._client_reader, PacketDirection.TO_CLIENT)
                # self.logger.debug(f"C <-  : {packet.type}")
                if await self.plugin_manager.hook_event(packet, self):
                    await self.write_to_client(packet)
        except (asyncio.IncompleteReadError, asyncio.CancelledError) as e:
            exception_text = "\n".join(format_exception(*e))
            self.logger.debug(f"Client connection was cancelled. Details:\n{exception_text}")

    async def send_message(self, message, *messages, mode=ChatReceiveMode.BROADCAST,
                           client_id=0, name="", channel=""):
        packet_data = {
            "message": message,
            "name": name,
            "junk": 0,
            "header": {
                "mode": mode,
                "channel": channel,
                "client_id": client_id
            }
        }
        # noinspection PyBroadException
        try:
            msg_packet = await Packet.from_parsed(PacketType.CHAT_RECEIVED, packet_data,
                                                  direction=PacketDirection.TO_CLIENT)
            await self.write_to_client(msg_packet)
        except Exception:
            self.logger.exception("Exception occurred while sending message packet.", exc_info=True)
        if messages:
            for message in messages:
                await self.send_message(message, mode=mode, client_id=client_id, name=name, channel=channel)

    async def write_to_server_raw(self, data):
        self._client_writer.write(data)
        await self._client_writer.drain()

    async def write_to_client_raw(self, data):
        self._writer.write(data)
        await self._writer.drain()

    async def write_to_server(self, packet):
        await self.write_to_server_raw(packet.original_data)

    async def write_to_client(self, packet):
        await self.write_to_client_raw(packet.original_data)

    def die(self):
        if self._alive:
            if hasattr(self, "player"):
                self.logger.info(f"Removing player {self.player.name} at IP {self.ip_address}.")
            else:
                self.logger.info(f"Removing connection from IP {self.ip_address}.")

