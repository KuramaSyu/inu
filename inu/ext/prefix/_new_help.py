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

import hikari
import lightbulb
from lightbulb import help_command
from lightbulb.context import Context
from lightbulb.commands import Command, PrefixCommand
from matplotlib.colors import cnames

from core import Inu
from utils import Paginator



class CustomHelp(help_command.BaseHelpCommand):
    def __init__(self, bot: lightbulb.BotApp):
        super().__init__(bot)
        self.cmds_per_list: int = 5
    async def send_bot_help(self, context: Context):
        await self.help(context)

    async def send_plugin_help(self, context: Context, plugin):
        pass

    async def send_command_help(self, context: Context, command):
        # Override this method to change the message sent when the help command
        # argument is the name or alias of a command.
        ...

    async def send_group_help(self, context: Context, group):
        # Override this method to change the message sent when the help command
        # argument is the name or alias of a command group.
        ...

    async def object_not_found(self, context: Context, obj):
        # Override this method to change the message sent when help is
        # requested for an object that does not exist
        ...

    async def help(self, ctx: Context):
        for name, cmd in self.bot.prefix_commands.items():
            pass

    async def create_cmd_description(self, cmd: PrefixCommand):
        desc = (
            f"```\n"
            f"{cmd.name}{cmd.}"
        )