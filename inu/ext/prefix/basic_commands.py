import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
import hikari
from numpy import isin


# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)

log = logging.getLogger(__name__)

basics = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)
if not isinstance(basics.d, lightbulb_utils.DataStore):
    raise RuntimeError("Plugin don't contain a datastore")
if basics.d is None:
    raise RuntimeError("Plugin don't contain a datastore")


@basics.command
@lightbulb.command("ping", "is the bot alive?")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def ping(ctx: context.Context):
    await ctx.respond("Bot is alive")


@basics.command
@lightbulb.option("to_echo", "the text I should echo", modifier=commands.OptionModifier.CONSUME_REST)
@lightbulb.command("echo", "echo your input")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def echo(ctx: context.Context):
    await ctx.respond(ctx.options.to_echo)

@echo.child
@lightbulb.option("to_echo", "the text I should echo", modifier=commands.OptionModifier.CONSUME_REST)
@lightbulb.option("multiplier", "How often should I repeat?", type=int)
@lightbulb.command("multiple", "echo your input multiple times")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def multiple(ctx):
    await ctx.respond(str(ctx.options.multiplier * ctx.options.to_echo))


def load(bot: lightbulb.BotApp):
    bot.add_plugin(basics)
