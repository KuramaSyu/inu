import random
import re
import typing
from typing import (
    List,
    Sequence,
    Union,
    Optional,
    Mapping,
    Dict,
)
import sys
import inspect
from inspect import isclass
import logging

import hikari
import lightbulb
from lightbulb import help_command
from lightbulb.context import Context
from lightbulb.commands import Command, PrefixCommand, PrefixCommandGroup, CommandLike
from matplotlib.colors import cnames
from pandas import options

from core import Inu
from utils import Paginator, Colors

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class CustomHelp(help_command.BaseHelpCommand):
    def __init__(self, bot: lightbulb.BotApp):
        super().__init__(bot)
        self.cmds_per_list: int = 5
    async def send_bot_help(self, context: Context):
        await self.help(context)

    async def send_plugin_help(self, context: Context, plugin):
        pass

    async def send_command_help(self, context: Context, command: Command):
        # Override this method to change the message sent when the help command
        # argument is the name or alias of a command.
        log.debug("command help started")
        dicts = [[self.command_to_dict(command, context)]]
        await self.dicts_to_pagination(dicts, context)

    async def send_group_help(self, context: Context, group):
        commands = self.group_to_commands(group, context)
        dicts = [self.commands_to_dicts(commands, context)]
        await self.dicts_to_pagination(dicts, context)


    async def object_not_found(self, context: Context, obj):
        # Override this method to change the message sent when help is
        # requested for an object that does not exist
        commands = self.search(obj)

    def search(self, obj) -> List[Command]:
        results = []
        for name, command in self.bot.prefix_commands.item():
            if obj in name:
                results.append(command)

        if not results:
            return self.search(obj[:-1])
        else:
            return results

    def group_to_commands(self, group: PrefixCommandGroup, ctx: Context):
        log.debug(group.subcommands)
        commands: List[Command] = [group]  # because the group is also a command
        for command in group.subcommands.values():
            if not command in commands:
                commands.append(command)
        log.debug(commands)
        return commands

    async def dicts_to_pagination(self, dicts: List[List[Dict[str, str]]], ctx: Context) -> None:
        """
        starts the pagination.

        Args
        ----
            - dicts (List[List[Dict[str, str]]]) A list which represents all embeds. The second List represents one embed
              The Dict inside the second List represents one field of the embed (mapping from name: value)
            - ctx: (Context) the context, to send the message(s)
        """
        embeds = []
        for i, prebuild in enumerate(dicts):
            name = prebuild[0]["group"]
            embed = hikari.Embed(title=f"Help {name}- {i+1}/{len(dicts)}")
            embed.description = "<...> required\n[...] optional"
            for field in prebuild:
                embed.add_field(field["sign"], field["description"])
            embed.color = Colors.random_color()
            embeds.append(embed)
        pag = Paginator(page_s=embeds, timeout=500)
        await pag.start(ctx)
            
    
    def commands_to_dicts(self, commands: List[CommandLike], ctx: Context) -> List[Dict[str, str]]:
        return [self.command_to_dict(command, ctx) for command in commands]


    def command_to_dict(self, command: Command, ctx: Context, group_name: str = None) -> Dict:
        """returns a string with the command signature, aliases and options"""
        return {
            "sign": f"\n{self._get_command_signature(command, ctx)}",
            "description": f"```{self._get_command_description(command)}```",
            "group": f" for Group: {group_name}" if group_name else ""
        }

    def _remove_defaults(self, cmd_signature: str) -> str:
        """removes defaults and <ctx>"""
        if (i:=cmd_signature.find("<ctx>")) != -1:
            cmd_signature = f"{cmd_signature[:i]}{cmd_signature[i+6:]}"
        start = cmd_signature.find("=")
        if start == -1:
            return cmd_signature
        end = []
        end.append(cmd_signature.find(">", start))
        end.append(cmd_signature.find("]", start))
        while -1 in end:
            end.remove(-1)

        to_remove = cmd_signature[start:min(end)]
        cmd_signature = re.sub(to_remove, '', cmd_signature)

        if "=" in cmd_signature:
            cmd_signature = self._remove_defaults(cmd_signature)
        return cmd_signature

    def _get_command_signature(self, command: Command, ctx: Context):
        full_invoke = command.qualname.replace(command.name, "")
        cmd_sign = self._remove_defaults(command.signature)
        signature = f"{ctx.prefix}{cmd_sign}" #{full_invoke} ..
        return signature

    def _get_command_description(self, command: Command) -> str:
        args = ""
        optional = []
        required = []
        aliases = ", ".join(command.aliases)
        cmd_invoke = f"{command.name}"
        args += f"'{cmd_invoke}' is equal to: {aliases}\n" if aliases else ''
        for name, option in command.options.items():
            if option.required:
                required.append(option)
            else:
                optional.append(option)
        if required:
            args += "< required >\n"
            for option in required:
                args += f"    {option.name}: {option.description}\n"
        if optional:
            args += "[ optional ]\n"
            for option in optional:
                args += f"    {option.name}: {option.description}\n"
        return args

    async def help(self, ctx: Context):
        for name, cmd in self.bot.prefix_commands.items():
            pass


def load(bot):
    bot.d.old_help_command = bot.help_command
    bot.help_command = CustomHelp(bot)

def unload(bot):
    bot.help_command = bot.d.old_help_command
    del bot.d.old_help_command