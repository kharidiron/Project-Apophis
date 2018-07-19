import inspect
import logging

from .decorators import EventHook
from .enums import PacketType
from .errors import CommandSyntaxError, UserPermissionError


class CommandDispatcher:
    def __init__(self, factory):
        self.factory = factory
        self.config_manager = factory.config_manager
        self.logger = logging.getLogger("starrypy.command_dispatcher")
        self.default_config = {
            "command_prefix": "/"
        }
        try:
            self.conf = factory.config_manager.config["command_dispatcher"]
        except KeyError:
            factory.config_manager.config["command_dispatcher"] = self.default_config
            self.conf = factory.config_manager.config["command_dispatcher"]
        self.commands = {}

    def register_plugin(self, plugin):
        for _, mth in inspect.getmembers(plugin, predicate=lambda x: inspect.ismethod(x) and hasattr(x, "command")):
            self.register(mth, mth.name.lower())

    def deregister_plugin(self, plugin):
        for _, mth in inspect.getmembers(plugin, predicate=lambda x: inspect.ismethod(x) and hasattr(x, "command")):
            self.deregister(mth, mth.name.lower())

    def register(self, fn, name, is_alias=False):
        """
        Register commands in the command list and handle conflicts. If it's an
        alias, we don't want it to overwrite non-alias commands. Otherwise,
        overwrite based on priority, and failing that, load order.
        :param fn: The command function, with its added information.
        :param name: The command's name, for indexing.
        :param is_alias: A boolean that tells the registrar not to overwrite other commands.
        :return: None.
        """
        self.logger.debug(f"Registering command {name} from {fn.__self__.name}.")

        if name in self.commands:
            oldfn = self.commands[name]
            if fn.priority >= oldfn.priority and not is_alias:
                self.commands[name] = fn
                self.logger.warning(f"Command {name} from {fn.__self__.name} overwrites command {oldfn.name} from "
                                    f"{oldfn.__self__.name}!")
            else:
                self.logger.warning(f"Command {oldfn.name} from {oldfn.__self__.name} overwrites command {name} from "
                                    f"{fn.__self__.name}!")
        else:
            self.commands[name] = fn

        if hasattr(fn, "aliases") and not is_alias:
            for alias in fn.aliases:
                self.register(fn, alias.lower(), is_alias=True)

    def deregister(self, fn, name, is_alias=False):
        """
        Deregister commands from the command list when their plugin is deactivated.
        :param fn: The command function, with its added information.
        :param name: The command's name, for indexing.
        :param is_alias: A boolean that tells the registrar not to overwrite other commands.
        :return: None.
        """
        self.logger.debug(f"Deregistering command {name} from {fn.__self__.name}.")

        if name in self.commands:
            oldfn = self.commands[name]
            # Make sure the command isn't another plugin's
            if fn == oldfn:
                del self.commands[name]
        else:
            self.logger.debug(f"Could not deregister command {name}, no such command!")

        if hasattr(fn, "aliases") and not is_alias:
            for alias in fn.aliases:
                self.deregister(fn, alias, is_alias=True)

    # noinspection PyBroadException
    async def run_command(self, command, packet, client):
        try:
            fn = self.commands[command]
        except KeyError:
            return
        try:
            await fn(packet, client)
        except CommandSyntaxError as e:
            err = e if e else "Invalid syntax."
            if fn.syntax:
                deco = self.conf["command_prefix"]
                await client.send_message(f"{err}\nSyntax: {deco}{fn.name} {fn.syntax}.")
            else:
                await client.send_message(err)
        except UserPermissionError as e:
            err = f"\n{e}" if str(e) else ""
            await client.send_message(f"You do not have permission to use this command.{err}")
        except Exception:
            self.logger.exception("Exception occurred in command. ", exc_info=True)
            await client.send_message("Error occurred while running command.")

    # Event hooks
    @EventHook(PacketType.CHAT_SENT, priority=99)
    async def command_check(self, packet, client):
        deco = self.conf["command_prefix"]
        content = packet.parsed_data["text"]
        if content.startswith(deco):
            cmd = content[len(deco):].split()[0].lower()
            if cmd in self.commands:
                await self.run_command(cmd, packet, client)
            else:
                await client.send_message(f"Command {cmd} does not exist. Try {deco}help for a list of commands.")
        return False


class Command:
    """
    Defines a decorator that encapsulates a chat command. Provides a common
    interface for all commands, including roles, documentation, usage syntax,
    and aliases.
    """

    def __init__(self, name, *aliases, perms=set(), doc=None, syntax=None, priority=0, category="other"):
        if syntax is None:
            syntax = ""
        if isinstance(syntax, list):
            syntax = " ".join(syntax)
        if doc is None:
            doc = ""
        if isinstance(perms, str):
            perms = {perms}
        self.name = name
        self.aliases = aliases
        self.category = category
        self.doc = doc
        self.syntax = syntax
        self.perms = perms
        self.priority = priority

    def __call__(self, f):
        """
        Whenever a command is called, its handling gets done here.

        :param f: The function the Command decorator is wrapping.
        :return: The now-wrapped command, with all the trappings.
        """

        async def wrapped(s, packet, client):
            #  user_perms = client.player.permissions
            user_perms = set()  # Player manager isn't implemented yet, so can't do permission checks.
            if not user_perms >= self.perms:
                raise UserPermissionError
            return await f(s, packet, client)

        wrapped.command = True
        wrapped.aliases = self.aliases
        wrapped.__doc__ = self.doc
        wrapped.name = self.name
        wrapped.perms = self.perms
        wrapped.syntax = self.syntax
        wrapped.priority = self.priority
        wrapped.category = self.category
        return wrapped
