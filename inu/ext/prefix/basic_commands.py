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
from lightbulb import commands, context
import hikari


# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)

log = logging.getLogger(__name__)

basics = lightbulb.Plugin("Plugin with basic commands")


@basics.command
@lightbulb.command("ping", "is the bot alive?")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def ping(ctx: context.Context):
    await ctx.respond("Bot is alive")
    

def load(bot: lightbulb.BotApp):
    bot.add_plugin(basics)
