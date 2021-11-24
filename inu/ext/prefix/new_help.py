import random
import re
import typing
from typing import (
    List,
    Sequence,
    Union,
    Optional,
    Mapping,
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
from utils import Paginator

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
        await context.respond(self.command_to_str(command, context))

    async def send_group_help(self, context: Context, group):
        log.debug("help group")
        # Override this method to change the message sent when the help command
        # argument is the name or alias of a command group.
        await context.respond(
            self.commands_to_str(
                self.group_to_commands(group, context),
                context,
                is_group=True,
            ),
            
        )

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
        
        

    def str_to_embed(self, pages: List[str]) -> List[hikari.Embed]:
        ...

    def group_to_commands(self, group: PrefixCommandGroup, ctx: Context):
        log.debug(group.subcommands)
        commands: List[Command] = [group]  # because the group is also a command
        for command in group.subcommands.values():
            if not command in commands:
                commands.append(command)
        log.debug(commands)
        return commands
    
    def commands_to_str(self, commands: List[CommandLike], ctx: Context, is_group: bool = False):
        s = ""
        if is_group:
            s += f"↓↓ {commands[0].name} - group ↓↓"
        s += "\n".join(self.command_to_str(command, ctx) for command in commands)
        if is_group:
            s += f"↑↑ {commands[0].name} - group ↑↑"
        return s

    def command_to_str(self, command: Command, ctx: Context):
        """returns a string with the command signature, aliases and options"""
        return f"```{self._get_command_signature(command, ctx)}\n\n{self._get_command_description(command)}```"

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