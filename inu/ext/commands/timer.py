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

from core import getLogger

plugin = lightbulb.Plugin("Reminders", "Extends commands with reminder/alarm commands")

# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)



log = getLogger(__name__)

plugin = lightbulb.Plugin("Timer", "Extends the commands with timing commands", include_datastore=True)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
