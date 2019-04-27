import shlex

from starrypy.command_dispatcher import Command
from starrypy.plugin_manager import BasePlugin


class InfoCommands(BasePlugin):
    name = "Info"
    description = "Informational commands"

    @Command("About",
             doc="Show a blurb")
    async def _about(self, packet, client):
        await client.send_message(f"About stuff goes here.")

    @Command("Help",
             doc="Display helpful information on commands.",
             syntax="(command)")
    async def _help(self, packet, client):
        s = shlex.split(packet.parsed_data['text'])
        cmd, args = s[0], s[1:]
        if not args:
            commands = list(client.plugin_manager.command_dispatcher.commands)
            await client.send_message(f"{', '.join(commands)}")
        else:
            await client.send_message("Information about single command goes here.")
