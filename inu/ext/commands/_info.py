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

plugin = lightbulb.Plugin("Info", "Provides info commands")