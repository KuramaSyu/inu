import asyncio
import logging
import typing
from datetime import datetime
from typing import *
from numpy import full, isin

import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils

from fuzzywuzzy import fuzz
from hikari import (
    ActionRowComponent, 
    Embed, 
    MessageCreateEvent, 
    embeds, 
    ResponseType, 
    TextInputStyle
)
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.messages import ButtonStyle
from jikanpy import AioJikan
from lightbulb import OptionModifier as OM
from lightbulb import commands, context
from lightbulb.context import Context
from matplotlib.style import available
from typing_extensions import Self


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Starboard", "/")
bot: Inu

@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    # insert to starboard
    ...

@plugin.listener(hikari.GuildReactionDeleteEvent)
async def on_reaction_remove(event: hikari.GuildReactionDeleteEvent):
    # delete from starboard
    ...

@plugin.listener(hikari.GuildMessageDeleteEvent)
async def on_message_remove(event: hikari.GuildMessageDeleteEvent):
    # delete from starboard
    ...

@plugin.listener(hikari.GuildLeaveEvent)
async def on_guild_leave(event: hikari.GuildLeaveEvent):
    # remove all starboards
    ...








def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

