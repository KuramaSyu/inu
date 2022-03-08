import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
from lightbulb import OptionModifier as OM
from lightbulb.context import Context
import hikari
from matplotlib.style import available
from numpy import full, isin
from fuzzywuzzy import fuzz

from utils import Colors, Human, Paginator, crumble, PollVote
from core import getLogger, Inu

log = getLogger(__name__)

plugin = lightbulb.Plugin("Polls")

active_polls: List[PollVote] = []
# at start init from database

@plugin.listener(lightbulb.events.LightbulbStartedEvent)
async def reinit_open_polls():
    pass

@plugin.command
@lightbulb.command("poll", "start a poll")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def make_poll(ctx: Context):
    pass