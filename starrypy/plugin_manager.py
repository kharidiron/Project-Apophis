import importlib
import importlib.util
import logging
from inspect import getmembers, isclass, ismethod
from pathlib import Path
from starrypy.enums import PacketType
from starrypy.parser import parse_packet

class PluginManager:
    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.plugin_manager")
        self.factory = factory
        self.config_manager = factory.config_manager
        self.modules = {}
        self.plugins = {}
        self.active_plugins = set()
        self.inactive_plugins = set()
        self.load_from_path(Path(self.config_manager.config["system_plugin_path"]))
        self.load_from_path(Path(self.config_manager.config["user_plugin_path"]))
        self.event_hooks = {str(packet): set() for packet in PacketType}
        self.resolve_dependencies()
        self.detect_event_hooks()

    def load_from_path(self, path):
        ignores = ("__init__", "__pycache__")
        loaded = set()
        for file in path.iterdir():
            if file.stem in ignores:
                continue
            if (file.suffix == ".py" or file.is_dir()) and str(file) not in loaded and not file.stem.startswith("_"):
                try:
                    mod = self._load_module(file)
                    self.load_plugin(mod)
                    loaded.add(str(file))
                except (SyntaxError, ImportError):
                    self.logger.exception(f"Exception encountered while loading plugin {file.stem}: ", exc_info=True)
                except FileNotFoundError:
                    self.logger.error(f"File {file.stem} missing when load attempted!")

    def _load_module(self, path):
        if path.is_dir():
            path /= "__init__.py"
        if not path.exists():
            raise FileNotFoundError
        name = f"plugins.{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.logger.debug(mod)
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
        class_list = set()
        for name, obj in getmembers(mod, predicate=isclass):
            if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                obj.factory = self.factory
                obj.config_manager = self.config_manager
                obj.plugin_manager = self
                obj.logger = logging.getLogger(f"starrypy.plugin.{obj.name}")
                class_list.add(obj)
        return class_list

    def resolve_dependencies(self):
        for plg in self.plugins.values():
            deps = set(plg.depends)
            loaded = set(self.plugins.values())
            if not deps.issubset(loaded):
                self.logger.error(f"Plugin {plg.name} is missing the following dependencies: {deps - loaded}.\n"
                                  f"It will not be activated.")
                del self.plugins[plg.name]

    def detect_event_hooks(self):
        for plg in self.plugins.values():
            hooks = getmembers(plg, lambda x: ismethod(x) and x.__name__ in self.event_hooks)
            self.logger.debug(hooks)
            for i in hooks:
                self.event_hooks[i[0]].add(i[1])
        self.logger.debug(f"Event hooks: {self.event_hooks}")

    async def hook_event(self, packet, connection):
        event = str(PacketType(packet["type"]))
        send_ahead = True
        if self.event_hooks[event]:
            packet = await parse_packet(packet)
            for func in self.event_hooks[event]:
                try:
                    if not (await func(packet, connection)):
                        send_ahead = False
                except Exception:
                    self.logger.exception(f"Exception occurred in plugin {func.__self__.name} on event {event}.",
                                          exc_info=True)
        return send_ahead

    def __repr__(self):
        return f"<PluginManager: Plugins: {self.plugins.keys()}, Active: {self.active_plugins}>"

class BasePlugin:
    name = "base_plugin"
    description = "Common base class for plugins."
    version = "0.0"
    depends = ()
    default_config = {}

    def activate(self):
        pass

    def deactivate(self):
        pass

    def __repr__(self):
        return f"<Plugin {self.name} v{self.version}>"