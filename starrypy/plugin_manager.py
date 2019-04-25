import importlib
import logging
from asyncio import create_task
from binascii import hexlify
from inspect import getmembers, isclass, ismethod
from pathlib import Path
from pprint import pformat
from sys import modules
from types import ModuleType

from .command_dispatcher import CommandDispatcher
from .enums import PacketType
from .parser import reap_packets


class PluginManager:
    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.plugin_manager")
        self.factory = factory
        self.config_manager = factory.config_manager
        self.modules = {}
        self.plugins = {}
        self.active_plugins = set()
        self.inactive_plugins = set()
        self.plugin_package = ModuleType("starrypy_plugins")
        self.plugin_package.__path__ = []
        modules["starrypy_plugins"] = self.plugin_package
        self.command_dispatcher = CommandDispatcher(factory)
        self.event_hooks = {packet: [] for packet in PacketType}
        self.additional_packet_hook_locations = (self.factory.player_manager, self.factory.world_manager,
                                                 self.command_dispatcher)
        self.reaper_task = None
        # At some point this is going to change with a portable-mode toggle, but for now we just do this
        self.load_all_plugins((self.config_manager.config["system_plugin_path"],
                               self.config_manager.config["user_plugin_path"]))

    def load_all_plugins(self, paths):
        self.plugin_package.__path__.extend(str(x) for x in paths)
        for path in paths:
            self.load_plugin_folder(path)
        self.detect_event_hooks(core=self.additional_packet_hook_locations)

    def load_plugin_folder(self, path):
        loaded = set()
        for file in path.iterdir():
            if (file.suffix == ".py" or file.is_dir()) and file not in loaded and not file.stem.startswith(("_", ".")):
                try:
                    mod = self._load_module(file.stem)
                    self.load_plugin(mod)
                    loaded.add(file)
                except (SyntaxError, ImportError):
                    self.logger.exception(f"Exception encountered while loading plugin {file.stem}: ", exc_info=True)
                except FileNotFoundError:
                    self.logger.error(f"File {file.stem} missing when load attempted!")

    def _load_module(self, name):
        mod = importlib.import_module(f"starrypy_plugins.{name}")
        self.modules[name] = mod
        self.logger.debug(f"Imported module {name}.")
        return mod

    def load_plugin(self, mod):
        self.logger.debug(f"Loading plugins from module {mod}.")
        classes = self._get_plugin_classes(mod)
        self.logger.debug(f"Plugin classes: {classes}")
        for obj in classes:
            self.plugins[obj.name] = obj()
            self.modules[obj.name] = mod
            self.logger.debug(obj)
            self.logger.debug(f"Loaded plugin {obj.name}.")

    def _get_plugin_classes(self, mod):
        def predicate(cls):
            return isclass(cls) and issubclass(cls, BasePlugin) and cls is not BasePlugin

        class_list = set()
        for name, obj in getmembers(mod, predicate=predicate):
            if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                obj.factory = self.factory
                obj.config_manager = self.config_manager
                obj.plugin_manager = self
                obj.logger = logging.getLogger(f"starrypy.plugin.{obj.name}")
                class_list.add(obj)
        return class_list

    def detect_event_hooks(self, core=tuple()):
        for plg in self.plugins.values():
            hooks = getmembers(plg, lambda x: ismethod(x) and hasattr(x, "event"))
            for i in hooks:
                self.event_hooks[i[1].event].append(i[1])
            self.command_dispatcher.register_plugin(plg)

        for mod in core:
            hooks = getmembers(mod, lambda x: ismethod(x) and hasattr(x, "event"))
            for i in hooks:
                self.event_hooks[i[1].event].append(i[1])

        for hooks in self.event_hooks.values():
            hooks.sort(key=lambda x: x.priority, reverse=True)
        self.logger.debug(f"Event hooks: {pformat(self.event_hooks)}")

    async def hook_event(self, packet, client):
        event = PacketType(packet.type)
        send_ahead = True
        if self.event_hooks[event]:
            # noinspection PyBroadException
            try:
                packet = await packet.parse()
                if not self.reaper_task:
                    self.reaper_task = create_task(reap_packets(60))
            except NotImplementedError:
                self.logger.debug(f"Packet of type {event.name} is not implemented.")
            except Exception:
                self.logger.exception(f"Packet of type {event.name} could not be parsed!", exc_info=True)
                self.logger.debug(f"Packet that caused the error: {hexlify(packet.original_data)}")
            for func in self.event_hooks[event]:
                # noinspection PyBroadException
                try:
                    if not (await func(packet, client)):
                        send_ahead = False
                except Exception:
                    self.logger.exception(f"Exception occurred in plugin {func.__self__.name} on event {event}.",
                                          exc_info=True)
            await packet.build_edits()
        return send_ahead

    def __repr__(self):
        return f"<PluginManager: Plugins: {self.plugins.keys()}, Active: {self.active_plugins}>"


class BasePlugin:
    name = "base_plugin"
    description = "Common base class for plugins."
    version = "0.0"
    default_config = {}

    def activate(self):
        pass

    def deactivate(self):
        pass

    def __repr__(self):
        return f"<Plugin {self.name} v{self.version}>"
