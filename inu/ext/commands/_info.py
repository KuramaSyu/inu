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

log = getLogger(__name__)

# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)


plugin = lightbulb.Plugin("Info", "Provides info commands")

@plugin.command
@lightbulb.command("sys", "get system information")
